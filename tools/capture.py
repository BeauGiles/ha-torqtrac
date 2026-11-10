#!/usr/bin/env python3
"""Capture raw TorqTrac BLE frames from a real Torqeedo motor.

    pip install bleak
    python3 tools/capture.py                      # find nearest "Torq*" device
    python3 tools/capture.py --address AA:BB:...  # (UUID on macOS)
    python3 tools/capture.py --seconds 300 --out capture.jsonl

Close the TorqTrac phone app first (the module accepts one connection).
While it runs, change throttle / note what the phone app shows (battery %,
power W, speed, range) and write those readings down with the timestamps printed
here; that is how voltage/current scaling and the unknown bytes get confirmed.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import pathlib
import sys
import time

from bleak import BleakClient, BleakScanner

_proto_path = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components"
    / "torqeedo_torqtrac"
    / "protocol.py"
)
_spec = importlib.util.spec_from_file_location("torqtrac_protocol", _proto_path)
proto = importlib.util.module_from_spec(_spec)
sys.modules["torqtrac_protocol"] = proto
_spec.loader.exec_module(proto)


async def find_device(address: str | None):
    if address:
        return await BleakScanner.find_device_by_address(address, timeout=20)
    print("Scanning for a device named Torq* ...")
    return await BleakScanner.find_device_by_filter(
        lambda d, adv: (d.name or "").startswith("Torq")
        or proto.SERVICE_UUID in [u.lower() for u in adv.service_uuids],
        timeout=30,
    )


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--address")
    ap.add_argument("--seconds", type=int, default=120)
    ap.add_argument("--out", default="capture.jsonl")
    args = ap.parse_args()

    device = await find_device(args.address)
    if device is None:
        sys.exit("No Torqeedo device found.")
    print(f"Found {device.name} {device.address}")

    assembler = proto.FrameAssembler()
    out = open(args.out, "a")

    def on_notify(char, payload: bytearray) -> None:
        now = time.time()
        out.write(json.dumps({"t": now, "char": str(char.uuid), "hex": bytes(payload).hex()}) + "\n")
        out.flush()
        frame = assembler.feed(char.uuid, bytes(payload))
        if frame is None:
            return
        d = proto.parse_frame(frame)
        stamp = time.strftime("%H:%M:%S", time.localtime(now))
        if d is None:
            print(f"{stamp} BAD/short frame ({len(frame)}B): {frame.hex()}")
            return
        print(
            f"{stamp} soc={d.battery_percent} V={d.voltage:.2f} A={d.current:.1f} "
            f"P={d.power_w}W spd={d.speed_knots}kn rng={d.range_nm}nm/{d.range_minutes}min "
            f"err={d.error_code} chg={d.charging}\n         raw={frame.hex()}"
        )

    async with BleakClient(device) as client:
        print("\n== GATT table ==")
        for svc in client.services:
            print(f"[service] {svc.uuid}")
            for ch in svc.characteristics:
                line = f"   {ch.uuid}  {','.join(ch.properties)}"
                if "read" in ch.properties:
                    try:
                        val = await client.read_gatt_char(ch)
                        line += f"  = {bytes(val)!r}"
                    except Exception as err:  # noqa: BLE001
                        line += f"  (read failed: {err})"
                print(line)
        print("\n== Streaming (Ctrl-C to stop) ==")
        await client.start_notify(proto.CHAR_DISPLAY_1, on_notify)
        await client.start_notify(proto.CHAR_DISPLAY_2, on_notify)
        try:
            await asyncio.sleep(args.seconds)
        except asyncio.CancelledError:
            pass
    print(f"Raw log appended to {args.out}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
