"""Sensors for Aseko Display RS485."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfLength, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AsekoDisplayConfigEntry
from .entity import AsekoDisplayEntity
from .protocol import AsekoDisplayFrame


@dataclass(frozen=True, kw_only=True)
class AsekoSensorDescription(SensorEntityDescription):
    value_fn: Callable[[AsekoDisplayFrame], float | str | int | None]


SENSORS: tuple[AsekoSensorDescription, ...] = (
    AsekoSensorDescription(
        key="ph",
        name="pH",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda f: f.ph,
    ),
    AsekoSensorDescription(
        key="chlorine",
        name="Chlorine",
        icon="mdi:flask",
        native_unit_of_measurement="mg/L",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda f: f.probe_a if f.has_cl_probe else None,
    ),
    AsekoSensorDescription(
        key="redox",
        name="Redox",
        icon="mdi:flash",
        native_unit_of_measurement="mV",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda f: (f.probe_a * 100 if f.probe_a is not None else None)
        if f.has_rx_probe and not f.has_cl_probe
        else None,
    ),
    AsekoSensorDescription(
        key="temperature",
        name="Water temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda f: f.temperature,
    ),
    AsekoSensorDescription(
        key="water_level",
        name="Water level",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:waves-arrow-up",
        value_fn=lambda f: f.water_level_cm,
    ),
    AsekoSensorDescription(
        key="ph_setpoint",
        name="pH setpoint",
        suggested_display_precision=1,
        value_fn=lambda f: f.ph_setpoint,
    ),
    AsekoSensorDescription(
        key="chlorine_setpoint",
        name="Chlorine setpoint",
        native_unit_of_measurement="mg/L",
        suggested_display_precision=1,
        value_fn=lambda f: f.chlorine_setpoint,
    ),
    AsekoSensorDescription(
        key="redox_setpoint",
        name="Redox setpoint",
        native_unit_of_measurement="mV",
        suggested_display_precision=0,
        value_fn=lambda f: f.redox_setpoint,
    ),
    AsekoSensorDescription(
        key="temperature_setpoint",
        name="Temperature setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda f: f.temperature_setpoint,
    ),
    AsekoSensorDescription(
        key="serial",
        name="Serial",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: f.serial_hex,
    ),
    AsekoSensorDescription(
        key="error_1",
        name="Error flags 1",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: f.error_1,
    ),
    AsekoSensorDescription(
        key="error_2",
        name="Error flags 2",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: f.error_2,
    ),
    AsekoSensorDescription(
        key="unit_type",
        name="Unit type",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: f"0x{f.unit_type:02X}",
    ),
    AsekoSensorDescription(
        key="level_byte",
        name="Level byte",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f: f.level_byte,
    ),
    AsekoSensorDescription(
        key="probe_b",
        name="Secondary probe value",
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        value_fn=lambda f: f.probe_b,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AsekoDisplayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(AsekoDisplaySensor(entry, desc) for desc in SENSORS)


class AsekoDisplaySensor(AsekoDisplayEntity, SensorEntity):
    """One decoded value."""

    entity_description: AsekoSensorDescription

    def __init__(
        self, entry: AsekoDisplayConfigEntry, description: AsekoSensorDescription
    ) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description
        self._attr_name = description.name

    @property
    def native_value(self) -> float | str | int | None:
        if self._frame is None:
            return None
        return self.entity_description.value_fn(self._frame)
