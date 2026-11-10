"""Torqeedo TorqTrac BLE frame parsing.

Pure Python (no Home Assistant imports) so it can be unit-tested and reused by
tools/capture.py.

Derived from decompiling the official Android TorqTrac app (BluetoothLeService,
TorqeedoBusMessage, CRC8). Fields marked INFERRED were not stated in the app and
must be confirmed against a real motor.
"""

from __future__ import annotations

from dataclasses import dataclass

SERVICE_UUID = "746f7271-7472-6163-5f64-6973706c6179"  # ASCII "torqtrac_display"
CHAR_DISPLAY_1 = "746f7271-7472-6163-5f64-6973706c5f31"
CHAR_DISPLAY_2 = "746f7271-7472-6163-5f64-6973706c5f32"

# Standard Device Information service characteristics (read once, best effort)
CHAR_MANUFACTURER = "00002a29-0000-1000-8000-00805f9b34fb"
CHAR_MODEL = "00002a24-0000-1000-8000-00805f9b34fb"
CHAR_DEVICE_NAME = "00002a00-0000-1000-8000-00805f9b34fb"

MIN_FRAME_LEN = 31  # CRC lives at index 30
CRC_START = 1
CRC_LEN = 29  # CRC covers bytes 1..29
CRC_INDEX = 30


def crc8_maxim(data: bytes, crc: int = 0) -> int:
    """Dallas/Maxim 1-Wire CRC-8 (poly 0x31 reflected = 0x8C), as in the app."""
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8C if crc & 1 else crc >> 1
    return crc & 0xFF


def _u16(data: bytes, i: int) -> int:
    return (data[i] << 8) | data[i + 1]


def _s16(data: bytes, i: int) -> int:
    value = _u16(data, i)
    return value - 0x10000 if value & 0x8000 else value


def _bit(data: bytes, byte_index: int, bit: int) -> bool:
    return bool(data[byte_index] & (1 << bit))


@dataclass(frozen=True)
class TorqtracData:
    """One decoded message. Optional fields are None when the motor flags them invalid."""

    raw: bytes
    error_code: int  # app shows the hex digits of byte 6 read as decimal (0x21 -> 21)
    charging: bool
    setup_mode: bool
    gps_searching: bool
    battery_percent: int | None
    voltage_raw: int  # INFERRED: units of 0.01 V
    current_raw: int  # INFERRED: signed, units of 0.1 A
    speed_knots: float | None
    range_nm: float | None
    range_minutes: int | None

    @property
    def voltage(self) -> float:
        return self.voltage_raw / 100

    @property
    def current(self) -> float:
        return self.current_raw / 10

    @property
    def power_w(self) -> int:
        # Same formula as the app: (raw_v * raw_a + 500) / 1000. It yields watts only
        # if voltage is 0.01 V and current is 0.1 A, which is what supports the
        # INFERRED scaling above.
        return (self.voltage_raw * self.current_raw + 500) // 1000


def _error_code(byte: int) -> int:
    text = f"{byte:x}"
    return int(text) if text.isdigit() else byte


def parse_frame(frame: bytes) -> TorqtracData | None:
    """Decode a concatenated display-1 + display-2 frame. None if too short / bad CRC."""
    if len(frame) < MIN_FRAME_LEN:
        return None
    if crc8_maxim(frame[CRC_START : CRC_START + CRC_LEN]) != frame[CRC_INDEX]:
        return None

    return TorqtracData(
        raw=bytes(frame),
        error_code=_error_code(frame[6]),
        charging=_bit(frame, 3, 2),
        setup_mode=_bit(frame, 3, 3),
        gps_searching=_bit(frame, 4, 4),
        battery_percent=frame[17] if _bit(frame, 4, 1) else None,
        voltage_raw=_u16(frame, 18),
        current_raw=_s16(frame, 20),
        speed_knots=_u16(frame, 22) / 100 if _bit(frame, 4, 5) else None,
        range_nm=_u16(frame, 24) / 10 if _bit(frame, 4, 6) else None,
        range_minutes=_u16(frame, 26) if _bit(frame, 4, 7) else None,
    )


class FrameAssembler:
    """The motor splits each message over two notify characteristics.

    Like the app, wait until both halves have arrived, concatenate display-1 then
    display-2, and emit the result.
    """

    def __init__(self) -> None:
        self._part1: bytes | None = None
        self._part2: bytes | None = None

    def feed(self, char_uuid: str, data: bytes) -> bytes | None:
        uuid = str(char_uuid).lower()
        if uuid == CHAR_DISPLAY_1:
            self._part1 = bytes(data)
        elif uuid == CHAR_DISPLAY_2:
            self._part2 = bytes(data)
        else:
            return None
        if self._part1 is None or self._part2 is None:
            return None
        frame = self._part1 + self._part2
        self._part1 = self._part2 = None
        return frame
