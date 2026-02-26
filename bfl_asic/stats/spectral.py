"""FFT-based spectral analysis of bit position time series.

Collects a time series of individual bit values (0 or 1) at selected
positions across sequential hashes, then applies the FFT to detect
any periodic structure.  Truly random data should produce a flat power
spectrum with no significant peaks.
"""

from __future__ import annotations

import numpy as np


class BitPositionTimeSeries:
    """Collects bit values at specific positions over sequential hashes.

    Uses a circular buffer for memory efficiency.
    """

    def __init__(
        self,
        positions: list[int] | None = None,
        buffer_size: int = 8192,  # Power of 2 for efficient FFT
    ) -> None:
        """
        Args:
            positions: Bit positions to track (default: 8 evenly spaced:
                [0, 32, 64, 96, 128, 160, 192, 224])
            buffer_size: Circular buffer size (should be power of 2)
        """
        self._positions = (
            positions
            if positions is not None
            else [0, 32, 64, 96, 128, 160, 192, 224]
        )
        self._buffer_size = buffer_size
        self._buffer = np.zeros(
            (buffer_size, len(self._positions)), dtype=np.int8
        )
        self._write_idx = 0
        self._total_ingested = 0

    def ingest(self, hash_input: bytes, hash_output: bytes) -> None:
        """Extract bit values at tracked positions and store in buffer."""
        bits = np.unpackbits(np.frombuffer(hash_output, dtype=np.uint8))
        self._buffer[self._write_idx % self._buffer_size] = bits[
            self._positions
        ]
        self._write_idx += 1
        self._total_ingested += 1

    @property
    def is_ready(self) -> bool:
        """True once the buffer has been filled at least once."""
        return self._total_ingested >= self._buffer_size

    @property
    def positions(self) -> list[int]:
        """Tracked bit position indices."""
        return list(self._positions)

    @property
    def buffer_size(self) -> int:
        """Size of the circular buffer."""
        return self._buffer_size

    def get_series(self, position_index: int) -> np.ndarray:
        """Get the time series for a specific tracked position index.

        Returns the buffer in chronological order (most recent at end).
        """
        if not self.is_ready:
            # Return what we have
            return self._buffer[: self._total_ingested, position_index].copy()
        # Circular buffer: reorder so oldest is first
        start = self._write_idx % self._buffer_size
        return np.roll(self._buffer[:, position_index], -start)


def compute_power_spectrum(
    time_series: BitPositionTimeSeries,
    position_index: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute FFT power spectrum for a single bit position.

    Returns ``(frequencies, power)`` arrays.

    * *frequencies*: normalised frequencies [0, 0.5] (Nyquist).
    * *power*: ``|FFT|^2 / N`` (power spectral density).
    """
    from scipy.fft import rfft, rfftfreq

    series = time_series.get_series(position_index)
    n = len(series)

    # Center the series (remove DC offset)
    centered = series - series.mean()

    fft_vals = rfft(centered)
    power = np.abs(fft_vals) ** 2 / n
    freqs = rfftfreq(n)

    return freqs, power


def compute_all_spectra(
    time_series: BitPositionTimeSeries,
) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """Compute power spectra for all tracked bit positions.

    Returns ``{position: (frequencies, power)}`` mapping.
    """
    result = {}
    for i, pos in enumerate(time_series.positions):
        result[pos] = compute_power_spectrum(time_series, i)
    return result


def detect_periodicity(
    frequencies: np.ndarray,
    power: np.ndarray,
    threshold_sigma: float = 5.0,
) -> list[dict]:
    """Identify statistically significant frequency peaks.

    Computes z-scores of power values.  Peaks above *threshold_sigma*
    standard deviations from the mean are flagged.

    For truly random data, should return an empty list.

    Returns list of dicts::

        {"frequency": float, "power": float, "z_score": float}
    """
    if len(power) < 3:
        return []

    # Skip DC component (index 0)
    ac_power = power[1:]
    ac_freqs = frequencies[1:]

    mean = ac_power.mean()
    std = ac_power.std()

    if std < 1e-15:
        return []

    z_scores = (ac_power - mean) / std

    peaks = []
    for i, z in enumerate(z_scores):
        if z > threshold_sigma:
            peaks.append(
                {
                    "frequency": float(ac_freqs[i]),
                    "power": float(ac_power[i]),
                    "z_score": float(z),
                }
            )

    return peaks
