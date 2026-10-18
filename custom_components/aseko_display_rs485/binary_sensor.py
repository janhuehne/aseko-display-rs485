"""Binary sensors for Aseko Display RS485 relay bits."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AsekoDisplayConfigEntry
from .entity import AsekoDisplayEntity
from .protocol import AsekoDisplayFrame


@dataclass(frozen=True, kw_only=True)
class AsekoBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[AsekoDisplayFrame], bool | None]


BINARIES: tuple[AsekoBinaryDescription, ...] = (
    AsekoBinaryDescription(
        key="filtration",
        name="Filtration",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda f: f.filtration,
    ),
    AsekoBinaryDescription(
        key="heating",
        name="Heating",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda f: f.heating,
    ),
    AsekoBinaryDescription(
        key="electrolysis",
        name="Electrolysis",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda f: f.electrolysis,
    ),
    AsekoBinaryDescription(
        key="filling",
        name="Filling",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda f: f.filling,
    ),
    AsekoBinaryDescription(
        key="algicide",
        name="Algicide dosing",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda f: f.algicide,
    ),
    AsekoBinaryDescription(
        key="ph_minus",
        name="pH− dosing",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda f: f.ph_minus,
    ),
    AsekoBinaryDescription(
        key="water_level_disconnected",
        name="Water level sensor disconnected",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: f.water_level_disconnected,
    ),
    AsekoBinaryDescription(
        key="water_level_over_range",
        name="Water level over 200 cm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: f.water_level_over_range,
    ),
    AsekoBinaryDescription(
        key="salt_hour_dose_exceeded",
        name="Hourly dose exceeded",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: bool(f.error_1 & 0x01) if f.is_salt else None,
    ),
    AsekoBinaryDescription(
        key="salt_time_correction_error",
        name="Time correction error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: bool(f.error_1 & 0x02) if f.is_salt else None,
    ),
    AsekoBinaryDescription(
        key="salt_no_probe_flow",
        name="No flow to probes",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: bool(f.error_1 & 0x04) if f.is_salt else None,
    ),
    AsekoBinaryDescription(
        key="salt_buffer_tank_empty",
        name="Buffer tank empty",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: bool(f.error_1 & 0x08) if f.is_salt else None,
    ),
    AsekoBinaryDescription(
        key="salt_buffer_tank_overflow",
        name="Buffer tank overflow",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: bool(f.error_1 & 0x10) if f.is_salt else None,
    ),
    AsekoBinaryDescription(
        key="salt_low_filling_speed",
        name="Low filling speed",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: bool(f.error_1 & 0x20) if f.is_salt else None,
    ),
    AsekoBinaryDescription(
        key="salt_high_electrode_power",
        name="High electrode power",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: bool(f.error_2 & 0x01) if f.is_salt else None,
    ),
    AsekoBinaryDescription(
        key="salt_low_salt_4_0",
        name="Salt below 4.0 g/L",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: bool(f.error_2 & 0x02) if f.is_salt else None,
    ),
    AsekoBinaryDescription(
        key="salt_low_salt_4_5",
        name="Salt below 4.5 g/L",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: bool(f.error_2 & 0x04) if f.is_salt else None,
    ),
    AsekoBinaryDescription(
        key="salt_low_ph_warning",
        name="pH below 7.3",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: bool(f.error_2 & 0x08) if f.is_salt else None,
    ),
    AsekoBinaryDescription(
        key="salt_low_ph_shutdown",
        name="Electrolysis stopped by low pH",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: bool(f.error_2 & 0x10) if f.is_salt else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AsekoDisplayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(AsekoDisplayBinarySensor(entry, desc) for desc in BINARIES)


class AsekoDisplayBinarySensor(AsekoDisplayEntity, BinarySensorEntity):
    """Relay / status bit."""

    entity_description: AsekoBinaryDescription

    def __init__(
        self, entry: AsekoDisplayConfigEntry, description: AsekoBinaryDescription
    ) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description
        self._attr_name = description.name

    @property
    def is_on(self) -> bool | None:
        if self._frame is None:
            return None
        return self.entity_description.value_fn(self._frame)
