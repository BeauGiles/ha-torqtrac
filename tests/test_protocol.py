import importlib.util
import pathlib
import unittest

_path = (
    pathlib.Path(__file__).parent.parent
    / "custom_components"
    / "torqeedo_torqtrac"
    / "protocol.py"
)
_spec = importlib.util.spec_from_file_location("protocol", _path)
protocol = importlib.util.module_from_spec(_spec)
import sys

sys.modules["protocol"] = protocol  # dataclasses needs the module registered
_spec.loader.exec_module(protocol)


def build_frame(**kw) -> bytes:
    f = bytearray(32)
    f[3] = kw.get("b3", 0)
    f[4] = kw.get("b4", 0)
    f[6] = kw.get("err", 0)
    f[17] = kw.get("pct", 0)
    f[18:20] = kw.get("v", 0).to_bytes(2, "big")
    f[20:22] = (kw.get("a", 0) & 0xFFFF).to_bytes(2, "big")
    f[22:24] = kw.get("spd", 0).to_bytes(2, "big")
    f[24:26] = kw.get("rng", 0).to_bytes(2, "big")
    f[26:28] = kw.get("mins", 0).to_bytes(2, "big")
    f[30] = protocol.crc8_maxim(bytes(f[1:30]))
    return bytes(f)


class ProtocolTests(unittest.TestCase):
    def test_crc_known_vector(self):
        # Dallas/Maxim CRC-8 check value for "123456789" is 0xA1
        self.assertEqual(protocol.crc8_maxim(b"123456789"), 0xA1)

    def test_parse_all_valid(self):
        # bits in byte 4: 1 battery, 5 speed, 6 range nm, 7 range min
        f = build_frame(
            b4=(1 << 1) | (1 << 5) | (1 << 6) | (1 << 7),
            pct=87, v=2590, a=100, spd=512, rng=123, mins=95, err=0x21,
        )
        d = protocol.parse_frame(f)
        self.assertIsNotNone(d)
        self.assertEqual(d.battery_percent, 87)
        self.assertAlmostEqual(d.voltage, 25.9)
        self.assertAlmostEqual(d.current, 10.0)
        self.assertEqual(d.power_w, 259)
        self.assertAlmostEqual(d.speed_knots, 5.12)
        self.assertAlmostEqual(d.range_nm, 12.3)
        self.assertEqual(d.range_minutes, 95)
        self.assertEqual(d.error_code, 21)
        self.assertFalse(d.charging)

    def test_invalid_flags_give_none(self):
        d = protocol.parse_frame(build_frame(pct=50, spd=100, rng=5, mins=5))
        self.assertIsNone(d.battery_percent)
        self.assertIsNone(d.speed_knots)
        self.assertIsNone(d.range_nm)
        self.assertIsNone(d.range_minutes)

    def test_flags(self):
        d = protocol.parse_frame(build_frame(b3=(1 << 2) | (1 << 3), b4=1 << 4))
        self.assertTrue(d.charging)
        self.assertTrue(d.setup_mode)
        self.assertTrue(d.gps_searching)

    def test_negative_current(self):
        d = protocol.parse_frame(build_frame(v=2600, a=-50))
        self.assertAlmostEqual(d.current, -5.0)

    def test_bad_crc_and_short(self):
        f = bytearray(build_frame())
        f[10] ^= 0xFF
        self.assertIsNone(protocol.parse_frame(bytes(f)))
        self.assertIsNone(protocol.parse_frame(b"\x00" * 10))

    def test_assembler(self):
        f = build_frame(pct=10)
        a = protocol.FrameAssembler()
        self.assertIsNone(a.feed(protocol.CHAR_DISPLAY_2, f[16:]))
        self.assertEqual(a.feed(protocol.CHAR_DISPLAY_1, f[:16]), f[:16] + f[16:])
        self.assertIsNone(a.feed(protocol.CHAR_DISPLAY_1, f[:16]))  # waits for next half


if __name__ == "__main__":
    unittest.main()
