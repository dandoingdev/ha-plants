"""Tests for HA Plants integration."""

import pathlib
import types
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import Integration
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_plants import (
    async_reload_entry,
    config_flow,
    ensure_ha_plants_www_layout,
)
from custom_components.ha_plants.const import DOMAIN


def test_ensure_ha_plants_www_layout_creates_directories(
    tmp_path: pathlib.Path,
) -> None:
    """Startup helper creates www/ha_plants/images under the config directory."""
    ensure_ha_plants_www_layout(str(tmp_path))
    assert (tmp_path / "www" / "ha_plants" / "images").is_dir()
    ensure_ha_plants_www_layout(str(tmp_path))
    assert (tmp_path / "www" / "ha_plants" / "images").is_dir()


@pytest.mark.asyncio
async def test_flow_user_init(hass) -> None:
    """Test the initialization of the form in the first step of the config flow."""

    # Registramos manualmente el flujo
    config_entries.HANDLERS[config_flow.DOMAIN] = config_flow.HAPlantsConfigFlow

    mock_integration = Integration(
        hass=hass,
        pkg_path="custom_components.ha_plants",
        file_path=pathlib.Path("custom_components/ha_plants/__init__.py"),
        manifest={
            "domain": config_flow.DOMAIN,
            "name": "HA Plants",
            "version": "1.0.0",
            "requirements": [],
            "dependencies": [],
            "after_dependencies": [],
            "is_built_in": False,
        },
        top_level_files={
            "custom_components/ha_plants/manifest.json",
            "custom_components/ha_plants/config_flow.py",
            "custom_components/ha_plants/const.py",
            "custom_components/ha_plants/ha_plants_entity.py",
            "custom_components/ha_plants/ha_plants_manager.py",
            "custom_components/ha_plants/services.yaml",
        },
    )

    mock_config_flow_module = types.SimpleNamespace()
    mock_config_flow_module.HAPlantsConfigFlow = config_flow.HAPlantsConfigFlow
    mock_integration.async_get_platform = mock.AsyncMock(
        return_value=mock_config_flow_module
    )

    # Carga componentes necesarios (sensor, etc)
    assert await async_setup_component(hass, "sensor", {})

    with (
        mock.patch(
            "homeassistant.loader.async_get_integration",
            return_value=mock_integration,
        ),
        mock.patch(
            "homeassistant.loader.async_get_integrations",
            return_value={config_flow.DOMAIN: mock_integration},
        ),
        mock.patch(
            "custom_components.ha_plants.ha_plants_manager.async_track_time_change",
            return_value=mock.Mock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )

    expected = {
        "context": {"source": "user"},
        "data": {},
        "description": None,
        "flow_id": mock.ANY,
        "minor_version": 1,
        "options": {},
        "result": mock.ANY,
        "subentries": (),
        "title": "HA Plants",
        "type": mock.ANY,
        "version": 1,
        "description_placeholders": None,
        "handler": "ha_plants",
    }
    assert expected == result

    await hass.config_entries.async_unload(result["result"].entry_id)


@pytest.mark.asyncio
async def test_options_flow_init_shows_menu(hass) -> None:
    """Configure integration opens a menu (reminders + plants) in the UI."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="HA Plants",
        data={"plants": {}},
        options={},
    )
    entry.add_to_hass(hass)

    flow = config_flow.HAPlantsOptionsFlow()
    flow.hass = hass
    flow.handler = entry.entry_id

    result = await flow.async_step_init()
    assert result["type"] == data_entry_flow.FlowResultType.MENU
    assert result["step_id"] == "init"


@pytest.mark.asyncio
async def test_async_reload_entry():
    hass = MagicMock(spec=HomeAssistant)
    entry = MagicMock(spec=ConfigEntry)

    with (
        patch(
            "custom_components.ha_plants.async_unload_entry",
            new_callable=AsyncMock,
        ) as mock_unload,
        patch(
            "custom_components.ha_plants.async_setup_entry",
            new_callable=AsyncMock,
        ) as mock_setup,
    ):
        await async_reload_entry(hass, entry)

        mock_unload.assert_awaited_once_with(hass, entry)
        mock_setup.assert_awaited_once_with(hass, entry)
