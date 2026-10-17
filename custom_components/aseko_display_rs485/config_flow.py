"""Config flow for Aseko Display RS485."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import (
    CONF_ALLOWED_HOST,
    DEFAULT_ALLOWED_HOST,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
)

STEP_USER = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Optional(CONF_ALLOWED_HOST, default=DEFAULT_ALLOWED_HOST): str,
    }
)


class AsekoDisplayConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER)

        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        allowed_host = user_input.get(CONF_ALLOWED_HOST) or None
        await self.async_set_unique_id(f"{host}:{port}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"Aseko Display RS485 ({host}:{port})",
            data={
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_ALLOWED_HOST: allowed_host,
            },
        )
