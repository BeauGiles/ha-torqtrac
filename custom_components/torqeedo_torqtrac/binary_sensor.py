"""Binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device import TorqtracDevice
from .entity import TorqtracEntity
from .protocol import TorqtracData


@dataclass(frozen=True, kw_only=True)
class TorqtracBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[TorqtracData], bool]


BINARY_SENSORS: tuple[TorqtracBinaryDescription, ...] = (
    TorqtracBinaryDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda d: d.charging,
    ),
    TorqtracBinaryDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.error_code != 0,
    ),
    TorqtracBinaryDescription(
        key="setup_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.setup_mode,
    ),
    TorqtracBinaryDescription(
        key="gps_searching",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.gps_searching,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: TorqtracDevice = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(TorqtracBinary(device, desc) for desc in BINARY_SENSORS)


class TorqtracBinary(TorqtracEntity, BinarySensorEntity):
    entity_description: TorqtracBinaryDescription

    def __init__(self, device: TorqtracDevice, description: TorqtracBinaryDescription) -> None:
        super().__init__(device, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def is_on(self) -> bool | None:
        data = self._device.data
        return None if data is None else self.entity_description.value_fn(data)
