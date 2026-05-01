"""HA Plants component for Home Assistant."""

import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import IntegrationNotLoaded
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import translation

from .const import DOMAIN, HA_PLANTS_MANAGER
from .ha_plants_manager import HAPlantsManager

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def ensure_ha_plants_www_layout(config_dir: str) -> None:
    """Ensure default HA Plants www image folder exists (www/ha_plants/images → /local/ha_plants/images/)."""
    path = os.path.join(config_dir, "www", DOMAIN, "images")
    os.makedirs(path, exist_ok=True)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the integration from a config entry."""

    await translation.async_load_integrations(hass, {DOMAIN})

    try:
        await hass.async_add_executor_job(
            ensure_ha_plants_www_layout, hass.config.config_dir
        )
    except OSError as err:
        _LOGGER.warning(
            "Could not create %s/www/%s/images (optional): %s",
            hass.config.config_dir,
            DOMAIN,
            err,
        )

    # Initialize the DOMAIN in hass.data if it doesn't exist
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # HA Plants manager (hass.data key is HA_PLANTS_MANAGER)
    manager = HAPlantsManager(hass, entry)
    await manager.async_init()

    hass.data[DOMAIN][HA_PLANTS_MANAGER] = manager

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload the HA Plants manager and its entities."""

    # Unload the platforms (e.g., sensor)
    try:
        await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    except IntegrationNotLoaded:
        pass

    # Cleanup manager
    manager: HAPlantsManager = hass.data[DOMAIN].pop(HA_PLANTS_MANAGER, None)
    if manager:
        await manager.async_unload()

    # Optionally remove the domain if empty
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Handle reloads of the config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
