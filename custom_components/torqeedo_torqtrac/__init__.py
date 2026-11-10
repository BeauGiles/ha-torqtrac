"""Torqeedo TorqTrac integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .device import TorqtracDevice

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    device = TorqtracDevice(
        hass, entry.data[CONF_ADDRESS], entry.data.get(CONF_NAME) or "Torqeedo"
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = device
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await device.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    device: TorqtracDevice = hass.data[DOMAIN][entry.entry_id]
    await device.async_stop()
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
