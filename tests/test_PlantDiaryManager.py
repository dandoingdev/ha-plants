# Tests for HAPlantsManager
from datetime import date, timedelta
from typing import Iterable
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.entity import Entity
from homeassistant.util.hass_dict import HassKey
from homeassistant.helpers.entity_values import EntityValues

from custom_components.ha_plants.const import (
    CONF_NOTIFY_ENTITY_ID,
    CONF_REMINDERS_ENABLED,
    CONF_REMINDER_PERSISTENT,
    DOMAIN,
    OPTION_REMINDER_LAST_SENT,
)
from custom_components.ha_plants.ha_plants_manager import HAPlantsManager

DATA_CUSTOMIZE: HassKey[EntityValues] = HassKey("hass_customize")


def create_test_hass():
    """Create a reusable Home Assistant instance with minimal mocks."""
    hass = MagicMock(spec=HomeAssistant)

    hass._added_entities = []
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock(return_value=None)
    hass.async_add_executor_job = AsyncMock()
    hass.data = {}
    hass.data[DATA_CUSTOMIZE] = {}
    hass.states = MagicMock()

    # Dictionary to store registered service handlers
    registered_services = {}

    def async_register(domain, service, handler, *args, **kwargs):
        if domain not in registered_services:
            registered_services[domain] = {}
        registered_services[domain][service] = handler

    async def async_call(domain, service, data, blocking=False, context=None):
        handler = registered_services[domain][service]
        await handler(ServiceCall(hass, domain, service, data, context))

    # Set up mock services object
    hass.services = MagicMock()
    hass.services.async_register = async_register
    hass.services.async_call = async_call
    hass.services.has_service = lambda d, s: s in registered_services.get(
        d, {}
    ) or (d == "notify" and s == "send_message") or (
        d == "persistent_notification" and s == "create"
    )

    def async_create_task(coro, *args, **kwargs):
        task = asyncio.create_task(coro)
        return task

    hass.async_create_task = async_create_task

    def add_entities(
        entities: Iterable[Entity], _update_before_add: bool = False
    ) -> None:
        """Mock synchronous add_entities (follows the protocol)."""
        for entity in entities:
            entity.hass = hass
            entity.entity_id = f"{DOMAIN}.{entity.name}"
            hass._added_entities.append(entity)
            # async_added_to_hass must be scheduled manually
            if hasattr(entity, "async_added_to_hass"):
                print("async_added_to_hass")
                hass.async_create_task(entity.async_added_to_hass())

    hass.async_add_entities = add_entities
    hass.config_entries = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    return hass


def test_plantdiarymanager_initialization() -> None:
    """Test the initialization of the manager."""
    hass = MagicMock(spec=HomeAssistant)
    entry = MagicMock(spec=ConfigEntry)
    manager = HAPlantsManager(hass, entry)
    assert manager is not None
    assert manager.hass == hass
    assert manager.entry == entry
    assert manager.entities == {}
    assert manager._async_add_entities is None
    assert manager._midnight_listener is None


@pytest.mark.asyncio
@patch("custom_components.ha_plants.ha_plants_manager.async_track_time_change")
async def test_plantdiarymanager_async_init(mock_async_track_time_change) -> None:
    """Test the async initialization of the manager."""
    hass = MagicMock(spec=HomeAssistant)

    # Add mock for hass.services.async_register
    hass.services = MagicMock()
    hass.services.async_register = MagicMock()

    entry = MagicMock(spec=ConfigEntry)
    entry.options = {}

    manager = HAPlantsManager(hass, entry)
    await manager.async_init()
    # Check if the method runs without errors
    assert manager is not None
    # Verify that the service was registered
    hass.services.async_register.assert_any_call(
        DOMAIN,
        "create_plant",
        ANY,
    )
    hass.services.async_register.assert_any_call(
        DOMAIN,
        "update_plant",
        ANY,
    )
    hass.services.async_register.assert_any_call(
        DOMAIN,
        "delete_plant",
        ANY,
    )
    hass.services.async_register.assert_any_call(
        DOMAIN,
        "update_days_since_watered",
        ANY,
    )
    assert manager._midnight_listener is not None
    assert mock_async_track_time_change.call_count == 2
    mock_async_track_time_change.assert_any_call(
        hass,
        manager.async_update_all_days_since_last_watered,
        hour=0,
        minute=0,
        second=1,
    )
    mock_async_track_time_change.assert_any_call(
        hass,
        manager.async_maybe_send_reminders,
        hour=9,
        minute=0,
        second=0,
    )

    assert manager._midnight_listener == mock_async_track_time_change.return_value


@pytest.mark.asyncio
@patch("custom_components.ha_plants.ha_plants_manager.async_track_time_change")
async def test_service_handlers_register_and_call(_mock_async_track_time_change):
    """Test registering and calling service handlers."""

    hass = create_test_hass()
    entry = MagicMock(spec=ConfigEntry)
    entry.options = {}
    manager = HAPlantsManager(hass, entry)

    # Patch the methods that the services would call
    manager.create_plant = AsyncMock()
    manager.update_plant = AsyncMock()
    manager.delete_plant = AsyncMock()
    manager.async_update_all_days_since_last_watered = AsyncMock()

    # Patch async_track_time_change to avoid lingering timers
    with patch("homeassistant.helpers.event.async_track_time_change"):
        await manager.async_register_services()

    # Simulate service calls
    await hass.services.async_call(
        DOMAIN,
        "create_plant",
        {"plant_id": "test_plant"},
        blocking=True,
    )
    manager.create_plant.assert_called_once()

    await hass.services.async_call(
        DOMAIN,
        "update_plant",
        {"plant_id": "test_plant", "new_name": "Updated"},
        blocking=True,
    )
    manager.update_plant.assert_called_once()

    await hass.services.async_call(
        DOMAIN,
        "delete_plant",
        {"plant_id": "test_plant"},
        blocking=True,
    )
    manager.delete_plant.assert_called_once()

    await hass.services.async_call(
        DOMAIN,
        "update_days_since_watered",
        {},
        blocking=True,
    )
    manager.async_update_all_days_since_last_watered.assert_called_once()


@pytest.mark.asyncio
async def test_plantdiarymanager_restore_and_add_entities() -> None:
    """Test restoring and adding entities."""
    hass = create_test_hass()
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "plants": {
            "test_plant": {
                "plant_name": "Test Plant",
                "last_watered": "2023-10-01",
                "last_fertilized": "2023-09-15",
                "watering_interval": 14,
                "watering_postponed": 0,
                "days_since_watered": 1,
                "inside": True,
            }
        }
    }
    manager = HAPlantsManager(hass, entry)
    await manager.restore_and_add_entities(hass.async_add_entities)
    await asyncio.sleep(1)  # Let the event loop run the async_added_to_hass task

    assert manager._async_add_entities is not None
    assert len(manager.entities) == 1
    assert "test_plant" in manager.entities


@pytest.mark.asyncio
async def test_plantdiarymanager_create_plant() -> None:
    """Test creating a new plant."""
    hass = create_test_hass()
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {}
    manager = HAPlantsManager(hass, entry)
    await manager.restore_and_add_entities(hass.async_add_entities)
    data = {
        "plant_name": "New Plant",
        "last_watered": "2023-10-01",
        "last_fertilized": "2023-09-15",
        "watering_interval": 14,
        "watering_postponed": 0,
        "inside": True,
    }
    with patch("homeassistant.components.logbook.async_log_entry", None):
        await manager.create_plant(data)
    assert "New Plant" in manager.entities
    assert manager.entities["New Plant"]._plant_name == "New Plant"


@pytest.mark.asyncio
async def test_plantdiarymanager_update_plant() -> None:
    """Test updating an existing plant."""
    hass = create_test_hass()
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "plants": {
            "Existing Plant": {
                "plant_name": "Existing Plant",
                "last_watered": "2023-10-01",
                "last_fertilized": "2023-09-15",
                "watering_interval": 14,
                "watering_postponed": 0,
                "days_since_watered": 1,
                "inside": True,
            }
        }
    }
    manager = HAPlantsManager(hass, entry)
    await manager.restore_and_add_entities(hass.async_add_entities)
    updated_data = {
        "plant_id": "Existing Plant",
        "last_watered": "2023-10-02",
        "last_fertilized": "2023-10-02",
        "watering_interval": 7,
        "watering_postponed": 0,
        "inside": False,
        "plant_name": "Updated Plant",
        "image": "Existing Plant",
    }

    with patch("homeassistant.components.logbook.async_log_entry", None):
        await manager.update_plant(updated_data)

    updatedPlant = manager.entities["Existing Plant"]
    assert updatedPlant._last_watered.isoformat() == "2023-10-02"
    assert updatedPlant._last_fertilized.isoformat() == "2023-10-02"
    assert updatedPlant._watering_interval == 7
    assert updatedPlant._watering_postponed == 0
    assert updatedPlant._inside is False
    assert updatedPlant._plant_name == "Updated Plant"
    assert updatedPlant._image == "Existing Plant"

    # Test updating with a non-existing plant
    updated_data = {"plant_id": "Non-Existing Plant"}
    await manager.update_plant(updated_data)


@patch("homeassistant.helpers.entity_registry.async_get")
@pytest.mark.asyncio
async def test_plantdiarymanager_delete_plant(mock_er_async_get) -> None:
    """Test deleting an existing plant."""
    hass = create_test_hass()
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "plants": {
            "Plant to Delete": {
                "plant_name": "Plant to Delete",
                "last_watered": "2023-10-01",
                "last_fertilized": "2023-09-15",
                "watering_interval": 14,
                "watering_postponed": 0,
                "days_since_watered": 1,
                "inside": True,
            }
        }
    }
    manager = HAPlantsManager(hass, entry)
    await manager.restore_and_add_entities(hass.async_add_entities)

    # Mock the entity to be deleted
    entity = manager.entities["Plant to Delete"]
    entity.async_remove = AsyncMock()

    # Mock the entity registry
    mock_eid = "sensor.ha_plants_plant_to_delete"
    fake_registry = MagicMock()
    fake_entry = MagicMock()
    fake_entry.entity_id = mock_eid

    fake_registry.async_get.return_value = fake_entry
    fake_registry.async_remove = MagicMock()
    mock_er_async_get.return_value = fake_registry

    with (
        patch("homeassistant.components.logbook.async_log_entry", None),
        patch.object(entity, "entity_id", mock_eid, create=True),
    ):
        await manager.delete_plant("Plant to Delete")

    assert "Plant to Delete" not in manager.entities
    fake_registry.async_remove.assert_called_once_with(mock_eid)

    # Call the delete method to a non-existing plant
    await manager.delete_plant("Plant to Delete")


@pytest.mark.asyncio
async def test_plantdiarymanager_update_days_since_watered() -> None:
    """Test updating days since last watered for all plants."""
    hass = create_test_hass()
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "plants": {
            "Plant to Update": {
                "plant_name": "Plant to Update",
                "last_watered": "2023-10-01",
                "last_fertilized": "2023-09-15",
                "watering_interval": 14,
                "watering_postponed": 0,
                "days_since_watered": 1,
                "inside": True,
            }
        }
    }
    manager = HAPlantsManager(hass, entry)
    await manager.restore_and_add_entities(hass.async_add_entities)
    await manager.async_update_all_days_since_last_watered(None)
    assert manager.entities["Plant to Update"]._days_since_watered > 1


@patch("homeassistant.helpers.entity_registry.async_get")
@pytest.mark.asyncio
async def test_plantdiarymanager_async_unload(mock_er_async_get) -> None:
    """Test unloading the manager."""
    hass = create_test_hass()
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "plants": {
            "Plant to Delete": {
                "plant_name": "Plant to Delete",
                "last_watered": "2023-10-01",
                "last_fertilized": "2023-09-15",
                "watering_interval": 14,
                "watering_postponed": 0,
                "days_since_watered": 1,
                "inside": True,
            }
        }
    }
    manager = HAPlantsManager(hass, entry)
    await manager.restore_and_add_entities(hass.async_add_entities)

    # Mock the entity to be deleted
    entity = manager.entities["Plant to Delete"]
    entity.async_remove = AsyncMock()

    # Mock the entity registry
    mock_eid = "sensor.ha_plants_plant_to_delete"
    fake_registry = MagicMock()
    fake_entry = MagicMock()
    fake_entry.entity_id = mock_eid

    fake_registry.async_get.return_value = fake_entry
    fake_registry.async_remove = MagicMock()
    mock_er_async_get.return_value = fake_registry

    with patch.object(entity, "entity_id", mock_eid, create=True):
        await manager.async_unload()
    assert manager._midnight_listener is None
    assert manager._reminder_listener is None
    assert manager._async_add_entities is None
    assert len(manager.entities) == 0


def _persist_entry_options(entry: MagicMock, **kwargs):
    """Simulate config_entries.async_update_entry updating options."""
    opts = kwargs.get("options")
    if opts is not None:
        entry.options = dict(opts)


@pytest.mark.asyncio
async def test_async_maybe_send_reminders_water_due() -> None:
    """Reminders send once per day when watering is due."""
    hass = create_test_hass()
    calls: list[tuple[str, str, dict]] = []

    async def track_call(domain, service, data, blocking=False, context=None):
        calls.append((domain, service, data))

    hass.services.async_call = track_call

    overdue = (date.today() - timedelta(days=10)).isoformat()
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "plants": {
            "Aloe": {
                "plant_name": "Aloe",
                "last_watered": overdue,
                "last_fertilized": "Unknown",
                "watering_interval": 3,
                "watering_postponed": 0,
                "fertilizing_interval": 0,
                "days_since_watered": 99,
                "inside": True,
                "image": "",
            }
        }
    }
    entry.options = {
        CONF_REMINDERS_ENABLED: True,
        CONF_NOTIFY_ENTITY_ID: "",
        CONF_REMINDER_PERSISTENT: True,
        OPTION_REMINDER_LAST_SENT: {},
    }
    hass.config_entries.async_update_entry = MagicMock(
        side_effect=lambda e, **kw: _persist_entry_options(e, **kw)
    )

    manager = HAPlantsManager(hass, entry)
    await manager.restore_and_add_entities(hass.async_add_entities)
    await manager.async_maybe_send_reminders()

    assert any(c[0] == "persistent_notification" for c in calls)
    hass.config_entries.async_update_entry.assert_called_once()

    calls.clear()
    await manager.async_maybe_send_reminders()
    assert calls == []


@pytest.mark.asyncio
async def test_async_maybe_send_reminders_fertilizing_due() -> None:
    """Fertilizing reminder when interval exceeded."""
    hass = create_test_hass()
    calls: list[tuple[str, str, dict]] = []

    async def track_call(domain, service, data, blocking=False, context=None):
        calls.append((domain, service, data))

    hass.services.async_call = track_call

    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "plants": {
            "Fern": {
                "plant_name": "Fern",
                "last_watered": date.today().isoformat(),
                "last_fertilized": (date.today() - timedelta(days=35)).isoformat(),
                "watering_interval": 14,
                "watering_postponed": 0,
                "fertilizing_interval": 30,
                "days_since_watered": 0,
                "inside": True,
                "image": "",
            }
        }
    }
    entry.options = {
        CONF_REMINDERS_ENABLED: True,
        CONF_NOTIFY_ENTITY_ID: "",
        CONF_REMINDER_PERSISTENT: True,
        OPTION_REMINDER_LAST_SENT: {},
    }
    hass.config_entries.async_update_entry = MagicMock(
        side_effect=lambda e, **kw: _persist_entry_options(e, **kw)
    )

    manager = HAPlantsManager(hass, entry)
    await manager.restore_and_add_entities(hass.async_add_entities)
    await manager.async_maybe_send_reminders()

    assert any(
        c[0] == "persistent_notification" and "fertilizing" in c[2].get("message", "")
        for c in calls
    )


@pytest.mark.asyncio
async def test_async_maybe_send_reminders_disabled() -> None:
    """No notifications when reminders are disabled."""
    hass = create_test_hass()
    calls: list[tuple[str, str, dict]] = []

    async def track_call(domain, service, data, blocking=False, context=None):
        calls.append((domain, service, data))

    hass.services.async_call = track_call

    overdue = (date.today() - timedelta(days=10)).isoformat()
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "plants": {
            "Aloe": {
                "plant_name": "Aloe",
                "last_watered": overdue,
                "last_fertilized": "Unknown",
                "watering_interval": 3,
                "watering_postponed": 0,
                "fertilizing_interval": 0,
                "days_since_watered": 99,
                "inside": True,
                "image": "",
            }
        }
    }
    entry.options = {
        CONF_REMINDERS_ENABLED: False,
        CONF_REMINDER_PERSISTENT: True,
        OPTION_REMINDER_LAST_SENT: {},
    }

    manager = HAPlantsManager(hass, entry)
    await manager.restore_and_add_entities(hass.async_add_entities)
    await manager.async_maybe_send_reminders()

    assert calls == []
