"""Pure builders/parsers for the Icarus serial mining protocol.

The Icarus protocol (ASICMiner Block Erupter, Antminer U-series, and the
BM1384 GekkoScience Compac all speak it) is deliberately minimal: write a
64-byte work unit, read back a 4-byte nonce. There is no command space --
the device only hashes (confirmed by falsification on real hardware,
2026-08-19).

Byte layout (from cgminer's driver-icarus.c): a 64-byte work unit is
``rev(midstate, 32) + 20-byte fill + rev(data, 12)``; the nonce reply is
4 bytes, big-endian on the wire. The ``GOLDEN_WORK`` / ``GOLDEN_NONCE``
pair is cgminer's detection self-test (Block 171874).

No I/O happens here.
"""
from __future__ import annotations

WORK_SIZE = 64
NONCE_SIZE = 4
IO_SPEED = 115200  # baud (Block Erupter / Antminer U)

# cgminer driver-icarus.c golden self-test.
GOLDEN_WORK = bytes.fromhex(
    "4679ba4ec99876bf4bfe086082b40025"
    "4df6c356451471139a3afa71e48f544a"
    "00000000000000000000000000000000"
    "0000000087320b1a1426674f2fa722ce"
)
GOLDEN_NONCE = 0x000187A2


def build_work(midstate: bytes, data: bytes) -> bytes:
    """Build a 64-byte Icarus work unit from *midstate* (32B) and *data* (12B).

    Mirrors cgminer: both fields are byte-reversed, separated by a 20-byte
    zero fill. Returns exactly ``WORK_SIZE`` bytes.
    """
    if len(midstate) != 32:
        raise ValueError(f"midstate must be 32 bytes, got {len(midstate)}")
    if len(data) != 12:
        raise ValueError(f"data must be 12 bytes, got {len(data)}")
    return midstate[::-1] + b"\x00" * 20 + data[::-1]


def parse_nonce(raw: bytes) -> int:
    """Parse a 4-byte Icarus nonce reply (big-endian) into an int."""
    if len(raw) != NONCE_SIZE:
        raise ValueError(f"nonce must be {NONCE_SIZE} bytes, got {len(raw)}")
    return int.from_bytes(raw, "big")


def linear_scan_hashrate(nonce_time_pairs) -> float | None:
    """Estimate hashrate in H/s from ``(nonce_position, arrival_time)`` pairs.

    A device that scans nonces linearly from 0 reaches position ``N`` after
    ``N / rate`` seconds, so ``nonce / time == rate``. Averages that estimate
    over every pair with a positive arrival time; returns ``None`` if no
    usable sample exists.
    """
    rates = [n / t for n, t in nonce_time_pairs if t > 0]
    if not rates:
        return None
    return sum(rates) / len(rates)


# --- Antminer U1/U2 (ANU) frequency control -----------------------------
#
# The bare Icarus protocol has no command space, but the Antminer U-series
# (IDENT_ANU, BM1380) DOES accept a chip register write to set the PLL clock
# -- the frequency lever the BFL Jalapeno firmware denied us. Ported verbatim
# from cgminer's driver-icarus.c (``set_anu_freq``, ``crc5``,
# ``anu_find_freqhex``). Unlike the Block Erupter, this is a real command; it
# is identity-gated in cgminer and must only be sent to an ANU device.
#
# VERIFIED on hardware (Antminer U1, device #3, 2026-08-28): an underclock
# sweep 200/150/100 MHz over IcarusSerialTransport scaled hashrate linearly at
# ~7.9 MH/s per MHz (the clock physically moves) and the read-reg command
# echoed back the exact PLL multiplier written. build_anu_set_freq drives a
# real U1 clock change; byte-exact from cgminer.

ANU_REF_MHZ = 25.0          # on-board reference crystal
ANT_U1_DEFFREQ = 200        # cgminer's U1 default target (MHz)


def crc5(data: bytes, len_bits: int) -> int:
    """5-bit CRC over the first *len_bits* bits of *data*, MSB-first.

    Verbatim port of cgminer's ``crc5`` (BM1380/BM1384 register commands):
    LFSR seeded all-ones, taps at bits 0/2 fed by ``crcin[4] ^ din``.
    """
    crcin = [1, 1, 1, 1, 1]
    j = 0x80
    k = 0
    ptr = 0
    for _ in range(len_bits):
        din = 1 if (data[ptr] & j) else 0
        crcout = [
            crcin[4] ^ din,
            crcin[0],
            crcin[1] ^ crcin[4] ^ din,
            crcin[2],
            crcin[3],
        ]
        j >>= 1
        k += 1
        if k == 8:
            j = 0x80
            k = 0
            ptr += 1
        crcin = crcout
    crc = 0
    if crcin[4]:
        crc |= 0x10
    if crcin[3]:
        crc |= 0x08
    if crcin[2]:
        crc |= 0x04
    if crcin[1]:
        crc |= 0x02
    if crcin[0]:
        crc |= 0x01
    return crc


def anu_freq_to_reg(target_mhz: float) -> int:
    """Find the 16-bit ANU PLL register nearest to *target_mhz*.

    Port of cgminer's ``anu_find_freqhex``: sweeps the PLL dividers
    ``fout = 25 * nf / (nr * no)`` (``no = 1<<od``, ``nr = n+1``,
    ``nf = m+1``) and packs the winner as
    ``(bs << 14) | (m << 7) | (n << 2) | od``. Returns on the first exact hit.
    """
    best_diff = 1000.0
    best_hex = 0
    for od in range(4):
        no = 1 << od
        for n in range(16):
            nr = n + 1
            for m in range(64):
                nf = m + 1
                fout = ANU_REF_MHZ * nf / (nr * no)
                if abs(fout - target_mhz) > best_diff:
                    continue
                bs = 1 if 500 <= (fout * no) <= 1000 else 0
                best_diff = abs(fout - target_mhz)
                best_hex = (bs << 14) | (m << 7) | (n << 2) | od
                if fout == target_mhz:
                    return best_hex
    return best_hex


def anu_reg_to_freq(reg: int) -> float:
    """Decode an ANU PLL register back to its output frequency (MHz).

    Inverse of :func:`anu_freq_to_reg`'s packing; used to verify a register
    round-trips to the intended clock.
    """
    od = reg & 0x3
    no = 1 << od
    n = (reg >> 2) & 0x1F
    nr = n + 1
    m = (reg >> 7) & 0x7F
    nf = m + 1
    return ANU_REF_MHZ * nf / (nr * no)


def build_anu_set_freq(target_mhz: float | None = None, *,
                       reg: int | None = None) -> bytes:
    """Build the 4-byte ANU set-frequency command ``[0x82, hi, lo, crc5]``.

    Pass either a *target_mhz* (converted via :func:`anu_freq_to_reg`) or a
    raw *reg*. ``0x82`` = write register 2 (``2 | 0x80``); the CRC covers the
    first 27 bits (the three data bytes plus 3 zero bits).
    """
    if reg is None:
        reg = anu_freq_to_reg(ANT_U1_DEFFREQ if target_mhz is None
                              else target_mhz)
    cmd = bytearray(4)
    cmd[0] = 0x82
    cmd[1] = (reg & 0xFF00) >> 8
    cmd[2] = reg & 0x00FF
    cmd[3] = crc5(bytes(cmd), 27)
    return bytes(cmd)


def build_anu_read_freq() -> bytes:
    """Build the 4-byte ANU read-back command ``[0x84, 0x00, 0x04, crc5]``.

    ``0x84`` = read register 4 (``4 | 0x80``); mirrors cgminer's ``rdreg_buf``.
    """
    cmd = bytearray(4)
    cmd[0] = 0x84
    cmd[1] = 0x00
    cmd[2] = 0x04
    cmd[3] = crc5(bytes(cmd), 27)
    return bytes(cmd)
