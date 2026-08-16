"""ZVX (set) / ZKX (get) ASIC frequency-factor commands.

Grounded in BFL's open-source firmware (``luke-jr/BitForce_SC``):

* **ZKX** (get) replies ``FREQ:<n>``. In that firmware
  ``ASIC_GetFrequencyFactor()`` is unimplemented and returns 0, so the
  current factor is generally NOT readable — observe the effect of a
  change through the ``ZCX`` census ``FREQUENCY`` field instead.
* **ZVX** (set) is a **double-stage** command: send ``ZVX``, read ``OK``,
  send a **length-prefixed payload** ``[0x04][4 data bytes little-endian]``,
  read ``OK``. The firmware's ``USB_wait_stream`` treats the first byte as
  a length indicator (bytes-to-follow), NOT data — sending a bare 4 bytes
  is read as "expect 255 bytes" and rejected with ``ERR:INVALID DATA``. The
  4 data bytes are masked to 16 bits and written to ASIC oscillator-control
  register ``0x60`` on every engine.

SAFETY: register ``0x60`` is a raw clock/PLL control word. The firmware
itself only ever writes the 10 known-good words in
:data:`ASIC_FREQUENCY_WORDS` (its thermal manager steps up/down that
ladder). Setting a word from the table is as safe as normal firmware
operation; an arbitrary word is an untested PLL configuration. There is
no read-back, so **restore by power-cycling** (resets to firmware
default). No I/O happens in this module.
"""
from __future__ import annotations

CMD_GET_FREQ: bytes = b"ZKX"
CMD_SET_FREQ: bytes = b"ZVX"

#: The firmware's known-good oscillator words, slow -> fast (index 0..9).
#: Verbatim from BitForce_SC/std_defs.c. 0xD555 ~= 250 MHz, 0xFF55 <= 227
#: MHz per the source comments; 0x0 is the slowest, 0x5555 the fastest.
ASIC_FREQUENCY_WORDS: tuple[int, ...] = (
    0x0000, 0xFFFF, 0xFFFD, 0xFFF5, 0xFFD5,
    0xFF55, 0xFD55, 0xF555, 0xD555, 0x5555,
)


def build_get_freq_factor() -> bytes:
    """`ZKX` — bare get-frequency-factor query."""
    return CMD_GET_FREQ


def build_set_freq_factor(word: int) -> tuple[bytes, bytes]:
    """Return ``(command, payload)`` for the ZVX double-stage exchange.

    The caller writes ``command`` (``ZVX``), reads ``OK``, writes
    ``payload``, then reads ``OK``. ``payload`` is length-prefixed:
    ``[0x04][word as 4 bytes LE]`` (the firmware reads the first byte as
    the data length). ``word`` must be a 16-bit value; the firmware masks
    to 16 bits. This does NOT validate that the word is a known-good one —
    see :func:`is_known_word`.
    """
    if not (0 <= word <= 0xFFFF):
        raise ValueError(f"frequency word must be 16-bit (0..0xFFFF), "
                         f"got {word}")
    data = word.to_bytes(4, "little")
    return CMD_SET_FREQ, bytes([len(data)]) + data


def is_known_word(word: int) -> bool:
    """True if *word* is one of the firmware's known-good oscillator words."""
    return word in ASIC_FREQUENCY_WORDS


def parse_freq_factor(raw: bytes) -> int | None:
    """Parse a ``ZKX`` reply (``FREQ:<n>``). Returns the int, or ``None``
    if no FREQ line is present. Real firmware returns 0 (unimplemented)."""
    for line in raw.decode("ascii", errors="replace").splitlines():
        s = line.strip()
        if s.upper().startswith("FREQ:"):
            try:
                return int(s.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None
