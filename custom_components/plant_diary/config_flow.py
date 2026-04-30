"""Config flow for the Plant Diary integration."""

from datetime import time
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
)


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


class PlantDiaryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for the Plant Diary integration."""

    def is_matching(self, other_flow: config_entries.ConfigFlow) -> bool:
        """Check if the other flow matches this config flow."""
        return getattr(other_flow, "DOMAIN", None) == DOMAIN

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return PlantDiaryOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the user step in the configuration flow."""
        existing_entries = self._async_current_entries()
        if existing_entries:
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="Plant Diary", data={})


class PlantDiaryOptionsFlow(config_entries.OptionsFlow):
    """Handle Plant Diary options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__()
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
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

        return self.async_show_form(step_id="init", data_schema=schema)
