"""Ambient environment telemetry -- Govee H5075 BLE temp/humidity sensors.

Every thermal characterization so far has had only the *device's own* internal
sensor (BFL ``ZLX``); there was no independent measure of the room. These
sensors close that gap -- an ambient reference to calibrate the on-die reading
against, to confirm both Jalapenos share an environment during A/B concurrent
runs, and to monitor a deliberate "raise ambient to reach error-onset" push.

The Govee H5075 broadcasts temperature/humidity/battery in its BLE
manufacturer-data advertisement (SIG company id ``0xEC88``); no pairing or
connection is needed -- you just listen. The packing (a single 24-bit int
encoding temp *and* humidity) is ported from the widely-used community decoder.

Pure decode below is fully tested; the ``bleak`` reader is lazy-imported and
UNVERIFIED against a real sensor (none in hand yet, 2026-08-22) -- validate the
manufacturer-data byte offsets against the physical H5075 when it arrives.
"""
from __future__ import annotations

from dataclasses import dataclass

H5075_COMPANY_ID = 0xEC88  # BLE SIG "company" id in the H5075 advertisement


@dataclass(frozen=True)
class H5075Reading:
    """One decoded H5075 sample."""
    temp_c: float
    humidity: float   # percent
    battery: int      # percent

    @property
    def temp_f(self) -> float:
        return self.temp_c * 9 / 5 + 32


def decode_h5075_packet(packet: int) -> tuple[float, float]:
    """Decode the 24-bit packed value into ``(temp_c, humidity_pct)``.

    Govee stuffs both readings into one integer: temperature is the value /
    10000 and humidity is ``value % 1000 / 10``. The top bit (``0x800000``)
    flags a negative temperature. (Temperature carries a little humidity-digit
    bleed in its low decimals -- this matches the reference decoder and the
    device's own rounding.)
    """
    negative = bool(packet & 0x800000)
    value = packet & 0x7FFFFF          # strip the sign bit before both maths
    temp_c = value / 10000.0
    if negative:
        temp_c = -temp_c
    humidity = (value % 1000) / 10.0
    return temp_c, humidity


def decode_h5075(payload: bytes) -> H5075Reading:
    """Decode an H5075 manufacturer-data *payload* into an :class:`H5075Reading`.

    *payload* is the bytes ``bleak`` hands back for company id
    ``H5075_COMPANY_ID`` -- i.e. everything after the 2-byte company id:
    ``[0x00, b1, b2, b3, battery, ...]``. The packed 24-bit value is bytes
    1..3 (big-endian); the battery percent is byte 4.
    """
    if len(payload) < 5:
        raise ValueError(
            f"H5075 payload too short: {len(payload)} bytes (need >=5)")
    packet = int.from_bytes(payload[1:4], "big")
    temp_c, humidity = decode_h5075_packet(packet)
    return H5075Reading(temp_c=temp_c, humidity=humidity, battery=payload[4])


def decode_h5075_from_mfg(mfg_data: dict[int, bytes]) -> H5075Reading | None:
    """Decode from a ``bleak`` ``manufacturer_data`` dict, or ``None``.

    Returns ``None`` if the advertisement carries no H5075 company id -- handy
    for filtering a stream of mixed BLE advertisements.
    """
    payload = mfg_data.get(H5075_COMPANY_ID)
    if payload is None:
        return None
    return decode_h5075(payload)


async def read_h5075(duration: float = 10.0,
                     address: str | None = None):
    """Listen for H5075 advertisements for *duration* seconds (needs ``bleak``).

    Yields ``(address, H5075Reading)`` as advertisements arrive; if *address*
    is given, only that sensor is reported. Lazy-imports ``bleak`` so the core
    install stays dependency-free. UNVERIFIED against hardware -- the byte
    offsets in :func:`decode_h5075` must be confirmed against a real sensor.
    """
    try:
        from bleak import BleakScanner
    except ImportError as e:  # pragma: no cover - needs the optional dep
        raise RuntimeError(
            "read_h5075 needs the 'bleak' package: pip install bleak") from e

    import asyncio

    out: "asyncio.Queue" = asyncio.Queue()

    def _cb(device, adv):  # pragma: no cover - needs BLE hardware
        if address is not None and device.address != address:
            return
        reading = decode_h5075_from_mfg(adv.manufacturer_data or {})
        if reading is not None:
            out.put_nowait((device.address, reading))

    scanner = BleakScanner(detection_callback=_cb)
    await scanner.start()
    try:
        loop = asyncio.get_event_loop()
        end = loop.time() + duration
        while loop.time() < end:  # pragma: no cover - needs BLE hardware
            try:
                yield await asyncio.wait_for(out.get(), timeout=end - loop.time())
            except asyncio.TimeoutError:
                break
    finally:
        await scanner.stop()
