"""Decode Aseko external-display RS485 27-byte frames.

Protocol notes (community / Aseko internal “New external display”):
57600 8N1, ~1 frame / 10 s, starts with 0x0A, XOR CRC seeded with 0xAA.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .const import FRAME_SIZE, FRAME_START

_LOGGER = logging.getLogger(__name__)


def xor_crc(payload: bytes) -> int:
    """CRC over the first 26 bytes (seed 0xAA)."""
    value = 0xAA
    for byte in payload[: FRAME_SIZE - 1]:
        value ^= byte
    return value & 0xFF


def frame_crc_ok(frame: bytes) -> bool:
    return len(frame) == FRAME_SIZE and xor_crc(frame) == frame[26]


@dataclass(slots=True, frozen=True)
class AsekoDisplayFrame:
    """Parsed display-bus frame."""

    raw: bytes
    unit_type: int
    has_cl_probe: bool
    has_rx_probe: bool
    is_salt: bool
    is_home: bool
    is_aqua: bool
    is_profi: bool
    ph: float | None
    probe_a: float | None
    probe_b: float | None
    temperature: float | None
    error_1: int
    error_2: int
    serial_hex: str
    serial_number: int
    level_byte: int
    ph_setpoint: float | None
    chlorine_setpoint: float | None
    redox_setpoint: float | None
    temperature_setpoint: float | None
    flocculant_setpoint: float | None
    relay: int | None
    ph_dosing: bool | None
    disinfectant_dosing: bool | None
    filtration: bool | None
    heating: bool | None
    filling: bool | None
    electrolysis: bool | None
    algicide: bool | None
    flocculant: bool | None
    ph_minus: bool | None
    electrolysis_direction: bool | None
    backwash_or_error: bool | None

    @property
    def disinfectant_setpoint(self) -> float | None:
        """Return the model-aware chlorine or redox setpoint."""
        if self.chlorine_setpoint is not None:
            return self.chlorine_setpoint
        return self.redox_setpoint


def _u16(frame: bytes, index: int) -> int:
    return (frame[index] << 8) | frame[index + 1]


def _scaled_u16(value: int, divisor: float) -> float | None:
    if value == 0xFFFF:
        return None
    return value / divisor


def _scaled_u8(value: int, divisor: float) -> float | None:
    if value == 0xFF:
        return None
    return value / divisor


def _relay_bit(relay: int | None, bit: int) -> bool | None:
    if relay is None:
        return None
    return bool(relay & (1 << bit))


def decode_frame(frame: bytes) -> AsekoDisplayFrame:
    """Parse one 27-byte frame. Raises ValueError if invalid."""
    if len(frame) != FRAME_SIZE:
        raise ValueError(f"expected {FRAME_SIZE} bytes, got {len(frame)}")
    if frame[0] != FRAME_START:
        raise ValueError(f"bad start byte {frame[0]:02x}")
    if not frame_crc_ok(frame):
        raise ValueError("CRC mismatch")

    unit_type = frame[1]
    has_cl_probe = bool(unit_type & 0x01)
    has_rx_probe = bool(unit_type & 0x02)
    is_aqua = bool(unit_type & 0x10)
    is_salt = bool(unit_type & 0x20)
    is_home = bool(unit_type & 0x40)
    is_profi = bool(unit_type & 0x80)

    # Community captures label bytes 12-17 as serial, but byte 16 carries level.
    serial_bytes = frame[11:15]
    serial_number = int.from_bytes(serial_bytes, "big")
    level_byte = frame[15]

    ph = _scaled_u16(_u16(frame, 2), 100.0)
    probe_a = _scaled_u16(_u16(frame, 4), 100.0)
    probe_b = _scaled_u16(_u16(frame, 6), 100.0)
    temperature = _scaled_u16(_u16(frame, 8), 10.0)
    if ph is not None and not 0 <= ph <= 14:
        _LOGGER.warning("Accepting CRC-valid frame with unusual pH value %.2f", ph)
    if temperature is not None and not -5 <= temperature <= 50:
        _LOGGER.warning(
            "Accepting CRC-valid frame with unusual temperature %.1f °C",
            temperature,
        )

    disinfectant_raw = frame[17]
    chlorine_setpoint = (
        _scaled_u8(disinfectant_raw, 10.0) if has_cl_probe else None
    )
    redox_setpoint = (
        float(disinfectant_raw * 10)
        if has_rx_probe and not has_cl_probe and disinfectant_raw != 0xFF
        else None
    )

    relay = None if frame[21] == 0xFF else frame[21]
    ph_dosing = None
    disinfectant_dosing = None
    filtration = None
    heating = None
    filling = None
    electrolysis = None
    algicide = None
    flocculant = None
    ph_minus = None
    electrolysis_direction = None
    backwash_or_error = None

    if is_salt:
        ph_dosing = _relay_bit(relay, 0)
        disinfectant_dosing = _relay_bit(relay, 1)
        backwash_or_error = _relay_bit(relay, 0)
        filling = _relay_bit(relay, 1)
        heating = _relay_bit(relay, 2)
        filtration = _relay_bit(relay, 3)
        electrolysis = _relay_bit(relay, 4)
        algicide = _relay_bit(relay, 5)
        electrolysis_direction = _relay_bit(relay, 6)
        ph_minus = _relay_bit(relay, 7)
    elif is_home:
        backwash_or_error = _relay_bit(relay, 0)
        filling = _relay_bit(relay, 1)
        heating = _relay_bit(relay, 2)
        filtration = _relay_bit(relay, 3)
        algicide = _relay_bit(relay, 4)
        flocculant = _relay_bit(relay, 5)
        disinfectant_dosing = _relay_bit(relay, 6)
        ph_minus = _relay_bit(relay, 7)
    elif is_aqua:
        ph_dosing = _relay_bit(relay, 0)
        disinfectant_dosing = _relay_bit(relay, 1)

    return AsekoDisplayFrame(
        raw=bytes(frame),
        unit_type=unit_type,
        has_cl_probe=has_cl_probe,
        has_rx_probe=has_rx_probe,
        is_aqua=is_aqua,
        is_salt=is_salt,
        is_home=is_home,
        is_profi=is_profi,
        ph=ph,
        probe_a=probe_a,
        probe_b=probe_b,
        temperature=temperature,
        error_1=frame[10],
        error_2=frame[23],
        serial_hex=serial_bytes.hex(),
        serial_number=serial_number,
        level_byte=level_byte,
        ph_setpoint=_scaled_u8(frame[16], 10.0),
        chlorine_setpoint=chlorine_setpoint,
        redox_setpoint=redox_setpoint,
        temperature_setpoint=float(frame[18]) if frame[18] != 0xFF else None,
        flocculant_setpoint=_scaled_u8(frame[19], 10.0),
        relay=relay,
        ph_dosing=ph_dosing,
        disinfectant_dosing=disinfectant_dosing,
        backwash_or_error=backwash_or_error,
        filling=filling,
        heating=heating,
        filtration=filtration,
        electrolysis=electrolysis,
        algicide=algicide,
        flocculant=flocculant,
        electrolysis_direction=electrolysis_direction,
        ph_minus=ph_minus,
    )


class FrameAssembler:
    """Reassemble 27-byte frames from a TCP byte stream."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self.bad_crc_count = 0

    def feed(self, data: bytes) -> list[bytes]:
        self._buf.extend(data)
        frames: list[bytes] = []
        while True:
            try:
                start = self._buf.index(FRAME_START)
            except ValueError:
                self._buf.clear()
                break
            if start:
                del self._buf[:start]
            if len(self._buf) < FRAME_SIZE:
                break
            candidate = bytes(self._buf[:FRAME_SIZE])
            if frame_crc_ok(candidate):
                frames.append(candidate)
                del self._buf[:FRAME_SIZE]
                continue
            # Bad CRC: skip this start byte and resync
            self.bad_crc_count += 1
            del self._buf[0]
        # Cap runaway buffer
        if len(self._buf) > FRAME_SIZE * 4:
            del self._buf[: -FRAME_SIZE]
        return frames
