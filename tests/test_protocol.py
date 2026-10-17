"""Tests for the Aseko display-bus protocol."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

COMPONENT_DIR = (
    Path(__file__).parents[1] / "custom_components" / "aseko_display_rs485"
)
PACKAGE_NAME = "_aseko_display_rs485_protocol_tests"
package = types.ModuleType(PACKAGE_NAME)
package.__path__ = [str(COMPONENT_DIR)]
sys.modules[PACKAGE_NAME] = package
spec = importlib.util.spec_from_file_location(
    f"{PACKAGE_NAME}.protocol", COMPONENT_DIR / "protocol.py"
)
assert spec is not None and spec.loader is not None
protocol = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = protocol
spec.loader.exec_module(protocol)

FrameAssembler = protocol.FrameAssembler
decode_frame = protocol.decode_frame
frame_crc_ok = protocol.frame_crc_ok
xor_crc = protocol.xor_crc

LIVE_SAMPLE = bytes.fromhex(
    "0a2102c7000c000c00ba0006906b2053470a190a3200ff000000e3"
)


def _frame(
    *,
    unit_type: int = 0x21,
    probe_a: int = 12,
    temperature: int = 186,
    disinfectant_setpoint: int = 10,
    relay: int = 0,
) -> bytes:
    raw = bytearray(27)
    raw[0] = 0x0A
    raw[1] = unit_type
    raw[2:4] = (711).to_bytes(2, "big")
    raw[4:6] = probe_a.to_bytes(2, "big")
    raw[6:8] = (0).to_bytes(2, "big")
    raw[8:10] = temperature.to_bytes(2, "big")
    raw[11:15] = bytes.fromhex("06906b20")
    raw[15] = 0x53
    raw[16] = 71
    raw[17] = disinfectant_setpoint
    raw[18] = 25
    raw[19] = 5
    raw[21] = relay
    raw[26] = xor_crc(raw)
    return bytes(raw)


def test_live_sample_crc_and_decode() -> None:
    assert frame_crc_ok(LIVE_SAMPLE)

    frame = decode_frame(LIVE_SAMPLE)

    assert frame.is_salt
    assert frame.has_cl_probe
    assert frame.ph == pytest.approx(7.11)
    assert frame.probe_a == pytest.approx(0.12)
    assert frame.temperature == pytest.approx(18.6)
    assert frame.serial_hex == "06906b20"
    assert frame.serial_number == 110_127_904
    assert frame.level_byte == 0x53
    assert frame.chlorine_setpoint == pytest.approx(1.0)
    assert frame.disinfectant_setpoint == pytest.approx(1.0)


def test_fragmentation_and_coalescing() -> None:
    assembler = FrameAssembler()

    assert assembler.feed(b"\x00\x01" + LIVE_SAMPLE[:9]) == []
    assert assembler.feed(LIVE_SAMPLE[9:20]) == []
    assert assembler.feed(LIVE_SAMPLE[20:] + LIVE_SAMPLE) == [
        LIVE_SAMPLE,
        LIVE_SAMPLE,
    ]


def test_bad_crc_resynchronizes_to_next_frame() -> None:
    bad = bytearray(_frame())
    bad[4] ^= 0x01
    good = _frame(probe_a=25)
    assembler = FrameAssembler()

    assert assembler.feed(bytes(bad) + good) == [good]
    assert assembler.bad_crc_count >= 1


def test_ff_relay_bits_are_unknown() -> None:
    frame = decode_frame(_frame(relay=0xFF))

    assert frame.relay is None
    assert frame.filtration is None
    assert frame.heating is None
    assert frame.filling is None
    assert frame.electrolysis is None
    assert frame.algicide is None
    assert frame.ph_minus is None


def test_chlorine_setpoint_divides_by_ten() -> None:
    frame = decode_frame(_frame(unit_type=0x21, disinfectant_setpoint=17))

    assert frame.chlorine_setpoint == pytest.approx(1.7)
    assert frame.redox_setpoint is None
    assert frame.disinfectant_setpoint == pytest.approx(1.7)


def test_redox_setpoint_multiplies_by_ten() -> None:
    frame = decode_frame(_frame(unit_type=0x12, disinfectant_setpoint=65))

    assert frame.chlorine_setpoint is None
    assert frame.redox_setpoint == pytest.approx(650)
    assert frame.disinfectant_setpoint == pytest.approx(650)


def test_00ff_measurements_remain_valid() -> None:
    frame = decode_frame(_frame(probe_a=0x00FF, temperature=0x00FF))

    assert frame.probe_a == pytest.approx(2.55)
    assert frame.temperature == pytest.approx(25.5)


def test_relay_bitmap_is_model_aware() -> None:
    home = decode_frame(_frame(unit_type=0x41, relay=0x30))
    salt = decode_frame(_frame(unit_type=0x21, relay=0x30))

    assert home.algicide is True
    assert home.flocculant is True
    assert home.electrolysis is None
    assert salt.algicide is True
    assert salt.electrolysis is True
    assert salt.flocculant is None
