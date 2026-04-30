"""Module for managing the HA Plants component."""

import logging
from datetime import datetime
from typing import Any

from homeassistant.util.dt import now as dt_now

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.logbook import async_log_entry, log_entry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change

from .const import (
    CONF_NOTIFY_ENTITY_ID,
    CONF_REMINDER_HOUR,
    CONF_REMINDER_MINUTE,
    CONF_REMINDER_PERSISTENT,
    CONF_REMINDERS_ENABLED,
    DEFAULT_REMINDER_HOUR,
    DEFAULT_REMINDER_MINUTE,
    DOMAIN,
    OPTION_REMINDER_LAST_SENT,
)
from .PlantDiaryEntity import PlantDiaryEntity

_LOGGER = logging.getLogger(__name__)


class PlantDiaryManager:
    """Manager class to handle multiple PlantDiaryEntity instances."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the PlantDiaryManager with Home Assistant instance and config entry."""
        self.hass = hass
        self.entry = config_entry
        self.entities = {}
        self._async_add_entities = None
        self._midnight_listener = None
        self._reminder_listener = None

    async def async_init(self):
        """Initialize the PlantDiaryManager by registering services."""
        await self.async_register_services()

    async def restore_and_add_entities(self, async_add_entities: AddEntitiesCallback):
        """Restore plant entities from config entry and add them to Home Assistant."""
        self._async_add_entities = async_add_entities
        plants_data = self.entry.data.get("plants", {})

        for plant_id, plant_data in plants_data.items():
            await self._add_plant_entity(plant_id, plant_data, save_to_config=False)

    async def async_register_services(self):
        """Register Home Assistant services for plant management."""

        async def handle_create_plant(call: ServiceCall):
            await self.create_plant(call.data)

        async def handle_update_plant(call: ServiceCall):
            await self.update_plant(call.data)

        async def handle_delete_plant(call: ServiceCall):
            await self.delete_plant(call.data["plant_id"])

        async def handle_update_days_since_last_watered(_call: ServiceCall):
            await self.async_update_all_days_since_last_watered()

        self.hass.services.async_register(DOMAIN, "create_plant", handle_create_plant)
        self.hass.services.async_register(DOMAIN, "update_plant", handle_update_plant)
        self.hass.services.async_register(DOMAIN, "delete_plant", handle_delete_plant)
        self.hass.services.async_register(
            DOMAIN, "update_days_since_watered", handle_update_days_since_last_watered
        )

        self._midnight_listener = async_track_time_change(
            self.hass,
            self.async_update_all_days_since_last_watered,
            hour=0,
            minute=0,
            second=1,
        )

        self._register_reminder_listener()

    def _register_reminder_listener(self) -> None:
        """Schedule daily reminders at the configured local time."""
        if self._reminder_listener is not None:
            self._reminder_listener()
            self._reminder_listener = None

        opts: dict[str, Any] = dict(self.entry.options)
        hour = int(opts.get(CONF_REMINDER_HOUR, DEFAULT_REMINDER_HOUR))
        minute = int(opts.get(CONF_REMINDER_MINUTE, DEFAULT_REMINDER_MINUTE))

        self._reminder_listener = async_track_time_change(
            self.hass,
            self.async_maybe_send_reminders,
            hour=hour,
            minute=minute,
            second=0,
        )

    async def create_plant(self, data: dict):
        """Create a new PlantDiaryEntity and add it."""
        plant_id = data["plant_name"]
        plant_data = {
            "plant_name": data.get("plant_name", plant_id),
            "last_watered": data.get("last_watered", "Unknown"),
            "last_fertilized": data.get("last_fertilized", "Unknown"),
            "watering_interval": data.get("watering_interval", 14),
            "watering_postponed": data.get("watering_postponed", 0),
            "fertilizing_interval": data.get("fertilizing_interval", 0),
            "inside": data.get("inside", True),
            "image": data.get("image", plant_id),
        }

        await self._add_plant_entity(plant_id, plant_data, save_to_config=True)

        entity = self.entities.get(plant_id)
        if entity:
            async_log_entry(
                self.hass,
                name="HA Plants",
                message=f"Added new plant: {plant_id}",
                domain=DOMAIN,
                entity_id=f"{entity.entity_id}",
            )

    async def update_plant(self, data: dict):
        """Update an existing plant."""
        plant_id = data["plant_id"]
        entity = self.entities.get(plant_id)
        if not entity:
            _LOGGER.error("Plant with ID %s not found", plant_id)
            return

        entity.update_from_dict(data)

        # Force update the entity state
        await entity.async_update_ha_state(True)

        # Store the new state in the configuration
        self.update_plant_in_config_entry(plant_id, entity.extra_state_attributes)

        async_log_entry(
            self.hass,
            name="HA Plants",
            message=f"Updated plant: {plant_id}",
            domain=DOMAIN,
            entity_id=f"{entity.entity_id}",
        )

    async def delete_plant(self, plant_id: str, update_config_entry: bool = True):
        """Delete a plant diary entity."""
        entity = self.entities.get(plant_id)
        if not entity:
            _LOGGER.error("Plant with ID %s not found", plant_id)
            return

        # Remove from config entry
        if update_config_entry:
            self.update_plant_in_config_entry(plant_id, None)

        # Remove the entity from Home Assistant
        await entity.async_remove()

        # Remove from entity registry (if registered)
        entity_registry = er.async_get(self.hass)
        entity_entry = entity_registry.async_get(entity.entity_id)
        if entity_entry:
            entity_registry.async_remove(entity_entry.entity_id)

        async_log_entry(
            self.hass,
            name="HA Plants",
            message=f"Deleted plant: {plant_id}",
            domain=DOMAIN,
            entity_id=f"{entity.entity_id}",
        )

        # Remove from the entities dictionary
        del self.entities[plant_id]

    def update_plant_in_config_entry(self, plant_id: str, plant_data: dict | None):
        """Update a plant in the config entry. When plant_data is none, the plant is removed."""
        raw_plants = dict(self.entry.data.get("plants", {}))
        all_plants = {}
        if isinstance(raw_plants, dict):
            all_plants = dict(raw_plants)

        if plant_data is None:
            del all_plants[plant_id]
        else:
            all_plants[plant_id] = plant_data

        self.hass.config_entries.async_update_entry(
            self.entry, data={"plants": all_plants}
        )

    async def _add_plant_entity(
        self, plant_id: str, plant_data: dict, save_to_config: bool = False
    ):
        """Create and add a PlantDiaryEntity."""
        entity = PlantDiaryEntity(plant_id, plant_data)
        self.entities[plant_id] = entity

        if self._async_add_entities:
            self._async_add_entities([entity])

        # Force update the entity state
        await entity.async_update_ha_state(True)

        # Store in the config entry if applicable
        if save_to_config:
            self.update_plant_in_config_entry(plant_id, entity.extra_state_attributes)

    async def async_update_all_days_since_last_watered(
        self, _now: datetime | None = None
    ):
        """Update the days since last watered for all plant entities."""

        _LOGGER.debug("update for all plants")
        for plant_id in list(self.entities.keys()):
            entity = self.entities[plant_id]

            # Force update the entity state and write it to home assistant
            await entity.async_update_ha_state(True)

            # Store the new state in the configuration
            self.update_plant_in_config_entry(plant_id, entity.extra_state_attributes)

        log_entry(
            self.hass,
            name="HA Plants",
            message="Updated days since last watered for all plants: "
            + str(len(self.entities)),
            domain=DOMAIN,
            entity_id=None,  # No specific entity ID for this log entry
        )

    async def async_maybe_send_reminders(self, _now: datetime | None = None) -> None:
        """Send watering/fertilizing reminders if enabled and due."""
        if not self.entry.options.get(CONF_REMINDERS_ENABLED):
            return

        today = dt_now().date().isoformat()
        opts: dict[str, Any] = dict(self.entry.options)
        last_sent: dict[str, str] = dict(opts.get(OPTION_REMINDER_LAST_SENT, {}))

        plant_ids = set(self.entities.keys())
        pruned_last: dict[str, str] = {}
        for key, value in last_sent.items():
            parts = key.split("|", 1)
            if parts and parts[0] in plant_ids:
                pruned_last[key] = value
        last_sent = pruned_last

        notify_entity = (opts.get(CONF_NOTIFY_ENTITY_ID) or "").strip()
        want_persistent = bool(opts.get(CONF_REMINDER_PERSISTENT, True))

        updated = False
        for plant_id, entity in self.entities.items():
            entity.update_days_since_last_watered()

            if entity.watering_reminder_due():
                key = f"{plant_id}|water"
                if last_sent.get(key) != today:
                    await self._async_send_reminder(
                        plant_id=plant_id,
                        plant_name=entity._plant_name,
                        kind="water",
                        notify_entity_id=notify_entity,
                        persistent=want_persistent,
                    )
                    last_sent[key] = today
                    updated = True

            if entity.fertilizing_reminder_due():
                key = f"{plant_id}|fert"
                if last_sent.get(key) != today:
                    await self._async_send_reminder(
                        plant_id=plant_id,
                        plant_name=entity._plant_name,
                        kind="fert",
                        notify_entity_id=notify_entity,
                        persistent=want_persistent,
                    )
                    last_sent[key] = today
                    updated = True

        if updated:
            new_opts = {**opts, OPTION_REMINDER_LAST_SENT: last_sent}
            self.hass.config_entries.async_update_entry(self.entry, options=new_opts)

    async def _async_send_reminder(
        self,
        *,
        plant_id: str,
        plant_name: str,
        kind: str,
        notify_entity_id: str,
        persistent: bool,
    ) -> None:
        """Deliver one reminder via notify and/or persistent_notification."""
        if kind == "water":
            title = "HA Plants"
            message = f"{plant_name} needs watering."
        else:
            title = "HA Plants"
            message = f"{plant_name} needs fertilizing."

        safe_id = plant_id.replace(" ", "_")
        notification_id = f"plant_diary_reminder_{safe_id}_{kind}"

        if notify_entity_id and self.hass.services.has_service("notify", "send_message"):
            await self.hass.services.async_call(
                "notify",
                "send_message",
                {
                    "entity_id": notify_entity_id,
                    "title": title,
                    "message": message,
                },
                blocking=False,
            )

        if persistent and self.hass.services.has_service(
            "persistent_notification", "create"
        ):
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": title,
                    "message": message,
                    "notification_id": notification_id,
                },
                blocking=False,
            )

    async def async_unload(self):
        """Unload the manager and remove all entities."""

        # Unload all entities
        for plant_id in list(self.entities.keys()):
            await self.delete_plant(plant_id, update_config_entry=False)

        if self._midnight_listener:
            self._midnight_listener()
            self._midnight_listener = None

        if self._reminder_listener:
            self._reminder_listener()
            self._reminder_listener = None

        if self._async_add_entities:
            self._async_add_entities = None
