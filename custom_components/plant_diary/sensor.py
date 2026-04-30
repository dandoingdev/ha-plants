"""Sensor platform for the HA Plants custom component.

This module sets up the HA Plants sensor platform and integrates it with Home Assistant.
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PLANT_DIARY_MANAGER
from .PlantDiaryManager import PlantDiaryManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the HA Plants sensor platform from a config entry."""
    _LOGGER.debug("Setting up HA Plants sensor platform")

    # Recuperar el manager desde hass.data
    manager: PlantDiaryManager = hass.data[DOMAIN].get(PLANT_DIARY_MANAGER)

    if manager:
        await manager.restore_and_add_entities(async_add_entities)
    else:
        _LOGGER.error("PlantDiaryManager not found in hass.data")
