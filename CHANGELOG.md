# Changelog

## 0.0.1

First experimental release. Not yet tested on real hardware.

- Automatic discovery of Torqeedo TorqTrac motors over Bluetooth LE (local push, no cloud).
- Sensors: battery %, voltage, current, power, GPS speed, range (nautical miles and minutes), error code, raw frame (disabled by default).
- Binary sensors: charging, fault, setup mode, GPS searching.
- Entities go unavailable when the link drops or no valid data arrives for 30 seconds.
- `tools/capture.py` for capturing raw frames from a real motor.
- Brand icons and logos.
- Voltage and current scaling is inferred from the official app and still unverified.
