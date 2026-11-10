"""BLE connection manager for a TorqTrac motor module."""

from __future__ import annotations

import asyncio
import logging
import time

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import RECONNECT_MAX, RECONNECT_MIN, SIGNAL_UPDATE, STALE_AFTER
from .protocol import (
    CHAR_DISPLAY_1,
    CHAR_DISPLAY_2,
    CHAR_MANUFACTURER,
    CHAR_MODEL,
    FrameAssembler,
    TorqtracData,
    parse_frame,
)

_LOGGER = logging.getLogger(__name__)


class TorqtracDevice:
    """Holds a persistent notify subscription and the latest decoded frame."""

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        self.hass = hass
        self.address = address
        self.name = name
        self.data: TorqtracData | None = None
        self.last_update: float = 0.0
        self.connected = False
        self.manufacturer: str | None = None
        self.model: str | None = None
        self._assembler = FrameAssembler()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._signal = SIGNAL_UPDATE.format(address=address)

    @property
    def signal(self) -> str:
        return self._signal

    @property
    def available(self) -> bool:
        return (
            self.connected
            and self.data is not None
            and time.monotonic() - self.last_update < STALE_AFTER
        )

    async def async_start(self) -> None:
        self._stop.clear()
        self._task = self.hass.async_create_background_task(
            self._run(), f"torqtrac {self.address}"
        )

    async def async_stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    # -- internals -----------------------------------------------------------

    def _notify(self) -> None:
        async_dispatcher_send(self.hass, self._signal)

    @callback
    def _on_notification(self, char, payload: bytearray) -> None:
        frame = self._assembler.feed(char.uuid, bytes(payload))
        if frame is None:
            return
        parsed = parse_frame(frame)
        if parsed is None:
            _LOGGER.debug("Dropped frame (short or bad CRC): %s", frame.hex())
            return
        self.data = parsed
        self.last_update = time.monotonic()
        self._notify()

    async def _run(self) -> None:
        delay = RECONNECT_MIN
        while not self._stop.is_set():
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if ble_device is None:
                await self._sleep(delay)
                delay = min(delay * 2, RECONNECT_MAX)
                continue
            try:
                await self._session(ble_device)
                delay = RECONNECT_MIN
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("TorqTrac %s connection error: %s", self.address, err)
                delay = min(delay * 2, RECONNECT_MAX)
            finally:
                self.connected = False
                self._assembler = FrameAssembler()
                self._notify()
            await self._sleep(delay)

    async def _sleep(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), seconds)
        except asyncio.TimeoutError:
            pass

    async def _session(self, ble_device: BLEDevice) -> None:
        disconnected = asyncio.Event()
        client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            self.name,
            disconnected_callback=lambda _c: disconnected.set(),
            ble_device_callback=lambda: bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            or ble_device,
        )
        try:
            await self._read_info(client)
            await client.start_notify(CHAR_DISPLAY_1, self._on_notification)
            await client.start_notify(CHAR_DISPLAY_2, self._on_notification)
            self.connected = True
            _LOGGER.debug("TorqTrac %s connected", self.address)
            self._notify()
            stop_wait = asyncio.create_task(self._stop.wait())
            dc_wait = asyncio.create_task(disconnected.wait())
            await asyncio.wait({stop_wait, dc_wait}, return_when=asyncio.FIRST_COMPLETED)
            stop_wait.cancel()
            dc_wait.cancel()
        finally:
            await client.disconnect()

    async def _read_info(self, client: BleakClient) -> None:
        for attr, uuid in (("manufacturer", CHAR_MANUFACTURER), ("model", CHAR_MODEL)):
            try:
                value = await client.read_gatt_char(uuid)
                setattr(self, attr, bytes(value).decode(errors="replace").strip("\x00 "))
            except Exception:  # noqa: BLE001 - optional
                pass
