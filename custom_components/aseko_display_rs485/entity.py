"""Shared entity base."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.util import dt as dt_util

from . import AsekoDisplayConfigEntry, signal_frame
from .const import DOMAIN, STALE_AFTER
from .protocol import AsekoDisplayFrame


class AsekoDisplayEntity(Entity):
    """Base entity updated from display frames."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: AsekoDisplayConfigEntry, key: str) -> None:
        self._entry = entry
        self._key = key
        self._frame: AsekoDisplayFrame | None = entry.runtime_data.last_frame
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = self._device_info(self._frame)

    @property
    def available(self) -> bool:
        last_update = self._entry.runtime_data.last_update
        return (
            self._frame is not None
            and last_update is not None
            and dt_util.utcnow() - last_update <= timedelta(seconds=STALE_AFTER)
        )

    def _device_info(self, frame: AsekoDisplayFrame | None) -> DeviceInfo:
        serial = frame.serial_hex if frame else None
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Aseko Display RS485",
            manufacturer="Aseko",
            model=self._model_name(frame),
            serial_number=serial,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _handle(frame: AsekoDisplayFrame | None) -> None:
            self._frame = frame
            if frame is not None:
                self._attr_device_info = self._device_info(frame)
                self._update_device_registry(frame)
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_frame(self._entry.entry_id), _handle
            )
        )
        if self._frame is not None:
            self._update_device_registry(self._frame)

    @staticmethod
    def _model_name(frame: AsekoDisplayFrame | None) -> str:
        if frame is None:
            return "ASIN Aqua"
        if frame.is_salt:
            return "ASIN Aqua Salt"
        if frame.is_home:
            return "ASIN Aqua Home"
        if frame.is_profi:
            return "ASIN Aqua Profi"
        return "ASIN Aqua"

    @callback
    def _update_device_registry(self, frame: AsekoDisplayFrame) -> None:
        metadata = (frame.serial_hex, self._model_name(frame))
        if self._entry.runtime_data.device_metadata == metadata:
            return
        device = self.device_entry
        if device is None:
            return
        registry = dr.async_get(self.hass)
        registry.async_update_device(
            device.id,
            model=metadata[1],
            serial_number=metadata[0],
        )
        self._entry.runtime_data.device_metadata = metadata
