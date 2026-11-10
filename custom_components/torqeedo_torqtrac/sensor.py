"""Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device import TorqtracDevice
from .entity import TorqtracEntity
from .protocol import TorqtracData


@dataclass(frozen=True, kw_only=True)
class TorqtracSensorDescription(SensorEntityDescription):
    value_fn: Callable[[TorqtracData], Any]


SENSORS: tuple[TorqtracSensorDescription, ...] = (
    TorqtracSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.battery_percent,
    ),
    # voltage/current scaling is INFERRED (0.01 V / 0.1 A) - verify on real hardware
    TorqtracSensorDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda d: d.voltage,
    ),
    TorqtracSensorDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.current,
    ),
    TorqtracSensorDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.power_w,
    ),
    TorqtracSensorDescription(
        key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KNOTS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.speed_knots,
    ),
    TorqtracSensorDescription(
        key="range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.NAUTICAL_MILES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.range_nm,
    ),
    TorqtracSensorDescription(
        key="range_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.range_minutes,
    ),
    TorqtracSensorDescription(
        key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.error_code,
    ),
    TorqtracSensorDescription(
        key="raw_frame",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.raw.hex(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: TorqtracDevice = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(TorqtracSensor(device, desc) for desc in SENSORS)


class TorqtracSensor(TorqtracEntity, SensorEntity):
    entity_description: TorqtracSensorDescription

    def __init__(self, device: TorqtracDevice, description: TorqtracSensorDescription) -> None:
        super().__init__(device, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def native_value(self):
        data = self._device.data
        return None if data is None else self.entity_description.value_fn(data)
