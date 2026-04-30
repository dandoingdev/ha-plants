"""Config flow for the HA Plants integration."""

from datetime import date, datetime, time
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_NOTIFY_ENTITY_ID,
    CONF_REMINDER_HOUR,
    CONF_REMINDER_MINUTE,
    CONF_REMINDER_PERSISTENT,
    CONF_REMINDERS_ENABLED,
    DEFAULT_REMINDER_HOUR,
    DEFAULT_REMINDER_MINUTE,
    DOMAIN,
    PLANT_DIARY_MANAGER,
)
from .PlantDiaryManager import PlantDiaryManager


def _coerce_reminder_time(value: Any) -> tuple[int, int]:
    """Return (hour, minute) from TimeSelector / time / dict / string."""
    if value is None:
        return DEFAULT_REMINDER_HOUR, DEFAULT_REMINDER_MINUTE
    if isinstance(value, time):
        return value.hour, value.minute
    if isinstance(value, dict):
        return int(value["hours"]), int(value["minutes"])
    if isinstance(value, str):
        parts = value.split(":")
        return int(parts[0]), int(parts[1])
    return DEFAULT_REMINDER_HOUR, DEFAULT_REMINDER_MINUTE


def _coerce_date_for_plant(value: Any) -> str:
    """Normalize to YYYY-MM-DD or Unknown for PlantDiaryEntity."""
    if value is None:
        return "Unknown"
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return "Unknown"
        if "T" in stripped:
            return stripped.split("T", 1)[0][:10]
        return stripped[:10] if len(stripped) >= 10 else stripped
    if isinstance(value, dict) and value.get("datetime"):
        return _coerce_date_for_plant(value["datetime"])
    return "Unknown"


def _plants_dict(entry: config_entries.ConfigEntry) -> dict[str, Any]:
    raw = entry.data.get("plants", {})
    return dict(raw) if isinstance(raw, dict) else {}


class PlantDiaryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for the HA Plants integration."""

    def is_matching(self, other_flow: config_entries.ConfigFlow) -> bool:
        """Check if the other flow matches this config flow."""
        return getattr(other_flow, "DOMAIN", None) == DOMAIN

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return PlantDiaryOptionsFlow()

    async def async_step_user(self, user_input=None):
        """Handle the user step in the configuration flow."""
        existing_entries = self._async_current_entries()
        if existing_entries:
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="HA Plants", data={})


class PlantDiaryOptionsFlow(config_entries.OptionsFlow):
    """Handle HA Plants options (reminders and plants) in the UI."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self._edit_plant_id: str | None = None
        self._delete_plant_id: str | None = None

    def _get_manager(self) -> PlantDiaryManager | None:
        return self.hass.data.get(DOMAIN, {}).get(PLANT_DIARY_MANAGER)

    def _finish_options_unchanged(self) -> config_entries.ConfigFlowResult:
        """Close the options flow without changing stored options."""
        return self.async_create_entry(title="", data=dict(self.config_entry.options))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Offer reminder settings or plant management."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "reminder_settings",
                "add_plant",
                "edit_plant",
                "delete_plant",
            ],
            sort=True,
        )

    async def async_step_reminder_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure reminder notifications."""
        if user_input is not None:
            hour, minute = _coerce_reminder_time(user_input.get("reminder_time"))
            opts = dict(self.config_entry.options)
            if CONF_NOTIFY_ENTITY_ID in user_input:
                raw_notify = user_input[CONF_NOTIFY_ENTITY_ID]
                notify_id = raw_notify.strip() if isinstance(raw_notify, str) else ""
            else:
                notify_id = opts.get(CONF_NOTIFY_ENTITY_ID, "")
            out = {
                CONF_REMINDERS_ENABLED: user_input[CONF_REMINDERS_ENABLED],
                CONF_REMINDER_HOUR: hour,
                CONF_REMINDER_MINUTE: minute,
                CONF_NOTIFY_ENTITY_ID: notify_id,
                CONF_REMINDER_PERSISTENT: user_input[CONF_REMINDER_PERSISTENT],
            }
            merged = {**opts, **out}
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )
            return self.async_create_entry(title="", data=merged)

        opts = self.config_entry.options
        hour = int(opts.get(CONF_REMINDER_HOUR, DEFAULT_REMINDER_HOUR))
        minute = int(opts.get(CONF_REMINDER_MINUTE, DEFAULT_REMINDER_MINUTE))

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_REMINDERS_ENABLED,
                    default=opts.get(CONF_REMINDERS_ENABLED, False),
                ): selector.BooleanSelector(),
                vol.Required(
                    "reminder_time",
                    default={"hours": hour, "minutes": minute, "seconds": 0},
                ): selector.TimeSelector(),
                vol.Optional(CONF_NOTIFY_ENTITY_ID): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["notify"], multiple=False)
                ),
                vol.Required(
                    CONF_REMINDER_PERSISTENT,
                    default=opts.get(CONF_REMINDER_PERSISTENT, True),
                ): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(step_id="reminder_settings", data_schema=schema)

    async def async_step_add_plant(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add a plant from the UI."""
        manager = self._get_manager()
        if manager is None:
            return self.async_abort(reason="integration_not_loaded")

        if user_input is not None:
            plant_name = (user_input.get("plant_name") or "").strip()
            if not plant_name:
                return self.async_show_form(
                    step_id="add_plant",
                    data_schema=self._add_plant_schema(),
                    errors={"base": "plant_name_required"},
                )
            await manager.create_plant(
                {
                    "plant_name": plant_name,
                    "last_watered": _coerce_date_for_plant(
                        user_input.get("last_watered")
                    ),
                    "last_fertilized": _coerce_date_for_plant(
                        user_input.get("last_fertilized")
                    ),
                    "watering_interval": user_input.get("watering_interval", 14),
                    "watering_postponed": user_input.get("watering_postponed", 0),
                    "fertilizing_interval": user_input.get("fertilizing_interval", 0),
                    "inside": user_input.get("inside", True),
                    "image": (user_input.get("image") or "").strip(),
                }
            )
            return self._finish_options_unchanged()

        return self.async_show_form(step_id="add_plant", data_schema=self._add_plant_schema())

    @staticmethod
    def _add_plant_schema(
        defaults: dict[str, Any] | None = None,
    ) -> vol.Schema:
        d = defaults or {}
        return vol.Schema(
            {
                vol.Required("plant_name", default=d.get("plant_name", "")): str,
                vol.Optional("last_watered"): selector.DateSelector(),
                vol.Optional("last_fertilized"): selector.DateSelector(),
                vol.Optional(
                    "watering_interval",
                    default=int(d.get("watering_interval", 14)),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=100, step=1, mode=selector.NumberSelectorMode.SLIDER)
                ),
                vol.Optional(
                    "watering_postponed",
                    default=int(d.get("watering_postponed", 0)),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=100, step=1, mode=selector.NumberSelectorMode.SLIDER)
                ),
                vol.Optional(
                    "fertilizing_interval",
                    default=int(d.get("fertilizing_interval", 0)),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=365, step=1, mode=selector.NumberSelectorMode.SLIDER)
                ),
                vol.Optional("inside", default=bool(d.get("inside", True))): selector.BooleanSelector(),
                vol.Optional("image", default=d.get("image", "")): selector.TextSelector(),
            }
        )

    def _edit_plant_pick_schema(self) -> vol.Schema:
        plants = _plants_dict(self.config_entry)
        options = [
            {"value": plant_id, "label": f"{data.get('plant_name', plant_id)} ({plant_id})"}
            for plant_id, data in sorted(plants.items(), key=lambda x: x[0].lower())
        ]
        return vol.Schema(
            {
                vol.Required("plant_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
                )
            }
        )

    async def async_step_edit_plant(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Pick a plant to edit."""
        plants = _plants_dict(self.config_entry)
        if not plants:
            return self.async_abort(reason="no_plants")

        if user_input is not None:
            self._edit_plant_id = user_input["plant_id"]
            return await self.async_step_edit_plant_details()

        return self.async_show_form(step_id="edit_plant", data_schema=self._edit_plant_pick_schema())

    async def async_step_edit_plant_details(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit fields for the selected plant."""
        manager = self._get_manager()
        if manager is None:
            return self.async_abort(reason="integration_not_loaded")

        plant_id = self._edit_plant_id
        if not plant_id:
            return await self.async_step_edit_plant()

        plants = _plants_dict(self.config_entry)
        plant_data = plants.get(plant_id)
        if not plant_data:
            self._edit_plant_id = None
            return await self.async_step_edit_plant()

        if user_input is not None:
            await manager.update_plant(
                {
                    "plant_id": plant_id,
                    "plant_name": user_input.get("plant_name", plant_data.get("plant_name", plant_id)),
                    "last_watered": _coerce_date_for_plant(user_input.get("last_watered")),
                    "last_fertilized": _coerce_date_for_plant(user_input.get("last_fertilized")),
                    "watering_interval": user_input.get("watering_interval", 14),
                    "watering_postponed": user_input.get("watering_postponed", 0),
                    "fertilizing_interval": user_input.get("fertilizing_interval", 0),
                    "inside": user_input.get("inside", True),
                    "image": (user_input.get("image") or "").strip(),
                }
            )
            self._edit_plant_id = None
            return self._finish_options_unchanged()

        # Defaults: parse known date strings for DateSelector if possible
        def _date_default(key: str) -> date | None:
            raw = plant_data.get(key)
            if raw in (None, "", "Unknown"):
                return None
            if isinstance(raw, str):
                try:
                    return datetime.strptime(raw[:10], "%Y-%m-%d").date()
                except ValueError:
                    return None
            return None

        defaults = {
            **plant_data,
            "last_watered": _date_default("last_watered"),
            "last_fertilized": _date_default("last_fertilized"),
        }
        return self.async_show_form(
            step_id="edit_plant_details",
            data_schema=self._add_plant_schema(defaults),
        )

    async def async_step_delete_plant(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Pick a plant to delete."""
        plants = _plants_dict(self.config_entry)
        if not plants:
            return self.async_abort(reason="no_plants")

        if user_input is not None:
            self._delete_plant_id = user_input["plant_id"]
            return await self.async_step_delete_confirm()

        return self.async_show_form(step_id="delete_plant", data_schema=self._edit_plant_pick_schema())

    async def async_step_delete_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm plant deletion."""
        manager = self._get_manager()
        if manager is None:
            return self.async_abort(reason="integration_not_loaded")

        plant_id = self._delete_plant_id
        if not plant_id:
            return await self.async_step_delete_plant()

        if user_input is not None:
            if not user_input.get("confirm_delete"):
                self._delete_plant_id = None
                return await self.async_step_delete_plant()
            await manager.delete_plant(plant_id)
            self._delete_plant_id = None
            return self._finish_options_unchanged()

        schema = vol.Schema(
            {
                vol.Required("confirm_delete", default=False): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="delete_confirm",
            data_schema=schema,
            description_placeholders={"plant_id": plant_id},
        )
