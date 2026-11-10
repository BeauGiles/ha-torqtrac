# Torqeedo TorqTrac for Home Assistant

[![Tests](https://github.com/BeauGiles/ha-torqtrac/actions/workflows/tests.yml/badge.svg)](https://github.com/BeauGiles/ha-torqtrac/actions/workflows/tests.yml)
[![hacs](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

Unofficial Home Assistant integration that reads a Torqeedo electric outboard's
**TorqTrac** Bluetooth LE telemetry locally - no cloud, no account.

> **Status: experimental / untested on hardware.** The protocol was reverse-engineered
> from the official Android app, and the author's motor had not arrived when this was
> written. Expect to confirm a few unit scalings. See [Unverified](#unverified) and
> please report what you see.

## Entities

| Entity | Type | Notes |
|---|---|---|
| Battery | sensor | %, only when the motor flags it valid |
| Battery voltage | sensor | V (scaling inferred) |
| Battery current | sensor | A (scaling inferred) |
| Power | sensor | W, same formula as the app |
| GPS speed | sensor | knots, only when flagged valid |
| Range | sensor | nautical miles, only when flagged valid |
| Remaining runtime | sensor | minutes, only when flagged valid |
| Charging | binary sensor | |
| Fault | binary sensor | on when the error code is non-zero |
| Error code | diagnostic sensor | see the app's error list below |
| Setup mode, GPS searching | diagnostic binary sensors | |
| Raw frame | diagnostic sensor | hex of the last frame; disabled by default |

## Requirements

- Home Assistant 2024.6 or newer with the Bluetooth integration working.
- A Bluetooth adapter on the HA host **or** an
  [ESPHome Bluetooth proxy](https://esphome.io/components/bluetooth_proxy.html)
  within range of the motor's TorqTrac module. This is local BLE, so the boat has to be
  near your proxy, such as at the dock.
- The module accepts **one Bluetooth connection at a time**. Close the TorqTrac phone
  app while Home Assistant is connected, or they will take turns disconnecting each other.
- No pairing or PIN is needed (the official app never pairs).

## Installation

### HACS (custom repository)
1. HACS > Integrations > menu > **Custom repositories**.
2. Add `https://github.com/BeauGiles/ha-torqtrac`, category **Integration**.
3. Install **Torqeedo TorqTrac**, then restart Home Assistant.

### Manual
Copy `custom_components/torqeedo_torqtrac` into your `config/custom_components/`
directory and restart Home Assistant.

## Setup

With the motor powered on and in range, it should appear under
**Settings > Devices & services** as a discovered device. Otherwise use
**Add Integration > Torqeedo TorqTrac** and pick it from the list.

## Unverified

These come from reading decompiled code rather than from a live motor:

- **Voltage = raw / 100 V, current = raw / 10 A.** The app computes watts as
  `(raw_v * raw_a + 500) / 1000`, which only gives watts with these scalings.
  Current is parsed as signed (the app treats it as unsigned).
- Whether **GPS speed** is produced by the motor or needs a phone feeding it.
- The meaning of bytes 0-2, 5, 7-16 and 28-29 of the frame.
- Behaviour on motors / module firmware other than the one the app targets.

## Help confirm it - capture data

```bash
pip install bleak
python3 tools/capture.py --seconds 300
```

It prints the GATT table, decoded frames, and appends raw notifications to
`capture.jsonl`. While it runs, write down what the phone app shows (battery %, watts,
speed, range) at idle and under throttle. Then open an issue with the capture,
your notes, and your motor/module model. Enabling the **Raw frame** sensor and
debug logging (`logger: logs: custom_components.torqeedo_torqtrac: debug`) also helps.

## Protocol notes

Derived from the Android app's `BluetoothLeService`, `TorqeedoBusMessage` and `CRC8`.

- Service `746f7271-7472-6163-5f64-6973706c6179` (ASCII `torqtrac_displ`+`ay`).
  Notify characteristics `746f7271-7472-6163-5f64-6973706c5f31` and `...5f32`.
- Each message arrives as two notifications. Concatenate display-1 then display-2 for a
  frame of at least 31 bytes.
- CRC-8 (Dallas/Maxim, poly 0x31 reflected) over bytes 1-29 must equal byte 30.
- Byte 3: bit 2 charging, bit 3 setup mode.
- Byte 4: bit 1 battery valid, bit 4 GPS searching, bit 5 speed valid,
  bit 6 range (nm) valid, bit 7 range (min) valid.
- Byte 6: error code (its hex digits are read as decimal, so `0x21` means code 21).
- Byte 17 battery %; 18-19 voltage; 20-21 current; 22-23 speed (/100 knots);
  24-25 range (/10 nm); 26-27 range (minutes). 16-bit values are big-endian.
- The app only listens; it never writes to the motor. This integration is read-only too.

### Error codes

From the official app's error messages. The **Error code** sensor shows the number; **Fault** turns on for any non-zero code.

| Code | Meaning |
|---:|---|
| 02 | Motor overheated |
| 03 / 04 | Motor tipped during operation |
| 05 | Motor or propeller blocked |
| 06 | Low voltage |
| 07 | Motor overcurrent |
| 08 | Circuitry overheated |
| 21 | Incorrect tiller or remote throttle calibration |
| 22 | Magnetic sensor error |
| 23 | Throttle out of alignment |
| 30 | Motor communication error |
| 32 | Tiller or remote throttle communication error |
| 33 | General communication error |
| 41 / 42 | Incorrect charging voltage |
| 43 | Battery empty |
| 45 | Battery overcurrent |
| 46 | Temperature error |
| 48 | Charging temperature error |
| 70 | Battery charging error |
| 71 | Battery temperature error |
| 72 | Battery circuitry overheated |
| 73 | Battery overcurrent |
| 74 | Charging error |
| 75 | Pyro-fuse blown |
| 76 | Low voltage |
| 77 | Voltage too high during charging |
| 78 | Battery over-charged |
| 79 | Electronic battery malfunction |
| 80 | Deep discharge |
| 81 | Water sensor deployed |
| 82 | Battery charge imbalance |

## Development

```bash
python3 tests/test_protocol.py
```

The frame parser (`protocol.py`) has no Home Assistant dependency and is unit tested.
The HA glue (`device.py`, platforms, config flow) has not yet been exercised in a running
Home Assistant instance.

## Disclaimer

Not affiliated with or endorsed by Torqeedo GmbH. "Torqeedo" and "TorqTrac" are
trademarks of their owner. Provided as-is under the MIT license; do not rely on it for
navigation or safety decisions.
