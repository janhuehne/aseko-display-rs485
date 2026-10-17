"""Aseko Display RS485 — local push from Waveshare on the display bus."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ALLOWED_HOST,
    CONF_HOST,
    CONF_PORT,
    DEFAULT_ALLOWED_HOST,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
    STALE_AFTER,
)
from .protocol import AsekoDisplayFrame
from .server import AsekoDisplayServer

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

type AsekoDisplayConfigEntry = ConfigEntry[AsekoDisplayRuntime]


@dataclass
class AsekoDisplayRuntime:
    """Runtime state for one config entry."""

    server: AsekoDisplayServer | None = None
    last_frame: AsekoDisplayFrame | None = None
    last_update: datetime | None = None
    cancel_stale_timer: Callable[[], None] | None = None
    device_metadata: tuple[str, str] | None = None


def signal_frame(entry_id: str) -> str:
    return f"{DOMAIN}_frame_{entry_id}"


async def async_setup_entry(hass: HomeAssistant, entry: AsekoDisplayConfigEntry) -> bool:
    host = entry.data.get(CONF_HOST, DEFAULT_HOST)
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    allowed_host = entry.options.get(
        CONF_ALLOWED_HOST,
        entry.data.get(CONF_ALLOWED_HOST, DEFAULT_ALLOWED_HOST),
    )
    allowed_host = allowed_host or None

    runtime = AsekoDisplayRuntime()

    @callback
    def _mark_stale(_now: datetime) -> None:
        runtime.cancel_stale_timer = None
        if runtime.last_update is None:
            return
        age = (dt_util.utcnow() - runtime.last_update).total_seconds()
        if age < STALE_AFTER:
            runtime.cancel_stale_timer = async_call_later(
                hass, STALE_AFTER - age, _mark_stale
            )
            return
        runtime.last_frame = None
        async_dispatcher_send(hass, signal_frame(entry.entry_id), None)

    async def _on_frame(frame: AsekoDisplayFrame) -> None:
        runtime.last_frame = frame
        runtime.last_update = dt_util.utcnow()
        if runtime.cancel_stale_timer is not None:
            runtime.cancel_stale_timer()
        runtime.cancel_stale_timer = async_call_later(
            hass, STALE_AFTER, _mark_stale
        )
        async_dispatcher_send(hass, signal_frame(entry.entry_id), frame)

    @callback
    def _on_disconnect() -> None:
        if runtime.cancel_stale_timer is not None:
            runtime.cancel_stale_timer()
            runtime.cancel_stale_timer = None
        runtime.last_frame = None
        async_dispatcher_send(hass, signal_frame(entry.entry_id), None)

    runtime.server = AsekoDisplayServer(
        host,
        port,
        on_frame=_on_frame,
        on_disconnect=_on_disconnect,
        allowed_host=allowed_host,
    )

    try:
        await runtime.server.start()
    except OSError as err:
        raise ConfigEntryNotReady(f"Cannot listen on {host}:{port}: {err}") from err

    entry.runtime_data = runtime
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await runtime.server.stop()
        if runtime.cancel_stale_timer is not None:
            runtime.cancel_stale_timer()
            runtime.cancel_stale_timer = None
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AsekoDisplayConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        if entry.runtime_data.cancel_stale_timer is not None:
            entry.runtime_data.cancel_stale_timer()
            entry.runtime_data.cancel_stale_timer = None
        if entry.runtime_data.server is not None:
            await entry.runtime_data.server.stop()
    return unload_ok
