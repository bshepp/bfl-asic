"""Tests for bfl_asic.stats.spectral -- FFT-based spectral analysis."""

from __future__ import annotations

import numpy as np
import pytest

from bfl_asic.stats.engine import SoftwareHashEngine
from bfl_asic.stats.spectral import (
    BitPositionTimeSeries,
    compute_all_spectra,
    compute_power_spectrum,
    detect_periodicity,
)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _fill_time_series(
    ts: BitPositionTimeSeries,
    count: int | None = None,
    start: int = 0,
) -> None:
    """Ingest *count* hashes from SoftwareHashEngine into *ts*."""
    if count is None:
        count = ts.buffer_size
    engine = SoftwareHashEngine(start=start)
    for inp, out in engine.hashes(count=count):
        ts.ingest(inp, out)


# -------------------------------------------------------------------
# BitPositionTimeSeries construction
# -------------------------------------------------------------------

class TestBitPositionTimeSeriesConstruction:
    """Tests for BitPositionTimeSeries defaults and custom parameters."""

    def test_default_positions(self):
        ts = BitPositionTimeSeries()
        assert ts.positions == [0, 32, 64, 96, 128, 160, 192, 224]

    def test_default_buffer_size(self):
        ts = BitPositionTimeSeries()
        assert ts.buffer_size == 8192

    def test_custom_positions(self):
        ts = BitPositionTimeSeries(positions=[0, 1, 2, 3])
        assert ts.positions == [0, 1, 2, 3]

    def test_custom_buffer_size(self):
        ts = BitPositionTimeSeries(buffer_size=256)
        assert ts.buffer_size == 256


# -------------------------------------------------------------------
# Ingestion and readiness
# -------------------------------------------------------------------

class TestBitPositionTimeSeriesIngest:
    """Tests for ingest, is_ready, and get_series."""

    def test_is_ready_false_initially(self):
        ts = BitPositionTimeSeries(buffer_size=64)
        assert ts.is_ready is False

    def test_is_ready_false_after_partial_fill(self):
        ts = BitPositionTimeSeries(buffer_size=64)
        _fill_time_series(ts, count=32)
        assert ts.is_ready is False

    def test_is_ready_true_after_full_fill(self):
        ts = BitPositionTimeSeries(buffer_size=64)
        _fill_time_series(ts, count=64)
        assert ts.is_ready is True

    def test_is_ready_true_after_overflow(self):
        ts = BitPositionTimeSeries(buffer_size=64)
        _fill_time_series(ts, count=100)
        assert ts.is_ready is True

    def test_get_series_length_before_ready(self):
        ts = BitPositionTimeSeries(buffer_size=64)
        _fill_time_series(ts, count=20)
        series = ts.get_series(0)
        assert len(series) == 20

    def test_get_series_length_when_ready(self):
        ts = BitPositionTimeSeries(buffer_size=64)
        _fill_time_series(ts, count=64)
        series = ts.get_series(0)
        assert len(series) == 64

    def test_get_series_length_after_overflow(self):
        ts = BitPositionTimeSeries(buffer_size=64)
        _fill_time_series(ts, count=100)
        series = ts.get_series(0)
        assert len(series) == 64

    def test_positions_property_returns_list_copy(self):
        ts = BitPositionTimeSeries(positions=[0, 10, 20])
        positions = ts.positions
        positions.append(999)
        assert ts.positions == [0, 10, 20]

    def test_series_values_are_binary(self):
        """Each value in the time series should be 0 or 1."""
        ts = BitPositionTimeSeries(buffer_size=64)
        _fill_time_series(ts, count=64)
        for i in range(len(ts.positions)):
            series = ts.get_series(i)
            assert set(series.tolist()).issubset({0, 1})


# -------------------------------------------------------------------
# compute_power_spectrum
# -------------------------------------------------------------------

class TestComputePowerSpectrum:
    """Tests for compute_power_spectrum."""

    def test_returns_tuple_of_two_arrays(self):
        ts = BitPositionTimeSeries(buffer_size=64)
        _fill_time_series(ts, count=64)
        result = compute_power_spectrum(ts, position_index=0)
        assert isinstance(result, tuple)
        assert len(result) == 2
        freqs, power = result
        assert isinstance(freqs, np.ndarray)
        assert isinstance(power, np.ndarray)

    def test_frequencies_start_at_zero(self):
        ts = BitPositionTimeSeries(buffer_size=64)
        _fill_time_series(ts, count=64)
        freqs, _power = compute_power_spectrum(ts, 0)
        assert freqs[0] == pytest.approx(0.0)

    def test_frequencies_end_near_nyquist(self):
        ts = BitPositionTimeSeries(buffer_size=64)
        _fill_time_series(ts, count=64)
        freqs, _power = compute_power_spectrum(ts, 0)
        assert freqs[-1] == pytest.approx(0.5)

    def test_power_is_non_negative(self):
        ts = BitPositionTimeSeries(buffer_size=64)
        _fill_time_series(ts, count=64)
        _freqs, power = compute_power_spectrum(ts, 0)
        assert np.all(power >= 0.0)

    def test_frequencies_and_power_same_length(self):
        ts = BitPositionTimeSeries(buffer_size=128)
        _fill_time_series(ts, count=128)
        freqs, power = compute_power_spectrum(ts, 0)
        assert len(freqs) == len(power)


# -------------------------------------------------------------------
# compute_all_spectra
# -------------------------------------------------------------------

class TestComputeAllSpectra:
    """Tests for compute_all_spectra."""

    def test_returns_dict_with_correct_keys(self):
        positions = [0, 32, 64]
        ts = BitPositionTimeSeries(positions=positions, buffer_size=64)
        _fill_time_series(ts, count=64)
        spectra = compute_all_spectra(ts)
        assert set(spectra.keys()) == {0, 32, 64}

    def test_each_value_is_freqs_power_tuple(self):
        ts = BitPositionTimeSeries(positions=[0, 128], buffer_size=64)
        _fill_time_series(ts, count=64)
        spectra = compute_all_spectra(ts)
        for pos, (freqs, power) in spectra.items():
            assert isinstance(freqs, np.ndarray)
            assert isinstance(power, np.ndarray)
            assert len(freqs) == len(power)


# -------------------------------------------------------------------
# detect_periodicity
# -------------------------------------------------------------------

class TestDetectPeriodicity:
    """Tests for detect_periodicity."""

    def test_few_peaks_for_random_sha256_data(self):
        """SHA-256 output should have no strong periodic structure.

        The power spectrum of white noise is exponentially distributed,
        which has heavier tails than Gaussian.  With ~4k frequency bins
        a handful of z > 5 outliers is expected statistically.  We
        verify that no peak exceeds a very high threshold (10 sigma)
        and that the total number of 5-sigma peaks is negligible
        compared to the number of frequency bins.
        """
        ts = BitPositionTimeSeries(buffer_size=8192)
        _fill_time_series(ts, count=8192)
        freqs, power = compute_power_spectrum(ts, position_index=0)

        # No peaks should exceed 10 sigma
        strong_peaks = detect_periodicity(freqs, power, threshold_sigma=10.0)
        assert strong_peaks == [], (
            f"Unexpected strong periodicity: {strong_peaks}"
        )

        # At 5 sigma the number of peaks should be very small
        # relative to the ~4k frequency bins
        weak_peaks = detect_periodicity(freqs, power, threshold_sigma=5.0)
        n_bins = len(power) - 1  # excluding DC
        assert len(weak_peaks) < n_bins * 0.01, (
            f"Too many 5-sigma peaks: {len(weak_peaks)} out of {n_bins} bins"
        )

    def test_detects_injected_periodicity(self):
        """Inject a sine wave into a fake time series and verify detection."""
        n = 8192
        # Create a signal with a strong periodic component at frequency 0.1
        freq_inject = 0.1
        t = np.arange(n)
        signal = (np.sin(2 * np.pi * freq_inject * t) > 0).astype(np.int8)

        # Build a minimal mock of BitPositionTimeSeries
        ts = BitPositionTimeSeries(positions=[0], buffer_size=n)
        ts._buffer[:, 0] = signal
        ts._total_ingested = n
        ts._write_idx = n

        freqs, power = compute_power_spectrum(ts, position_index=0)
        peaks = detect_periodicity(freqs, power, threshold_sigma=5.0)
        assert len(peaks) >= 1
        # The dominant peak should be near the injected frequency
        dominant = max(peaks, key=lambda p: p["power"])
        assert abs(dominant["frequency"] - freq_inject) < 0.01

    def test_peak_dict_has_expected_keys(self):
        """Each peak dict should have frequency, power, z_score."""
        n = 1024
        freq_inject = 0.25
        t = np.arange(n)
        signal = (np.sin(2 * np.pi * freq_inject * t) > 0).astype(np.int8)

        ts = BitPositionTimeSeries(positions=[0], buffer_size=n)
        ts._buffer[:, 0] = signal
        ts._total_ingested = n
        ts._write_idx = n

        freqs, power = compute_power_spectrum(ts, position_index=0)
        peaks = detect_periodicity(freqs, power, threshold_sigma=3.0)
        assert len(peaks) >= 1
        for peak in peaks:
            assert "frequency" in peak
            assert "power" in peak
            assert "z_score" in peak

    def test_returns_empty_for_short_input(self):
        """Less than 3 power values should return empty."""
        freqs = np.array([0.0, 0.5])
        power = np.array([1.0, 1.0])
        assert detect_periodicity(freqs, power) == []

    def test_returns_empty_for_constant_power(self):
        """When all AC power values are identical (zero std), return empty."""
        freqs = np.linspace(0, 0.5, 100)
        power = np.ones(100) * 0.5
        peaks = detect_periodicity(freqs, power, threshold_sigma=3.0)
        assert peaks == []

    def test_z_score_above_threshold(self):
        """All returned peaks must have z_score above threshold."""
        n = 1024
        t = np.arange(n)
        signal = (np.sin(2 * np.pi * 0.2 * t) > 0).astype(np.int8)

        ts = BitPositionTimeSeries(positions=[0], buffer_size=n)
        ts._buffer[:, 0] = signal
        ts._total_ingested = n
        ts._write_idx = n

        freqs, power = compute_power_spectrum(ts, position_index=0)
        threshold = 4.0
        peaks = detect_periodicity(freqs, power, threshold_sigma=threshold)
        for peak in peaks:
            assert peak["z_score"] > threshold
