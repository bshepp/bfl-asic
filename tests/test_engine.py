"""Tests for bfl_asic.stats.engine -- HashSource ABC and software engines."""

from __future__ import annotations

import hashlib
import itertools
import struct

import pytest

from bfl_asic.stats.engine import (
    HashSource,
    SequentialInputEngine,
    SoftwareHashEngine,
)


# -------------------------------------------------------------------
# HashSource ABC
# -------------------------------------------------------------------

class TestHashSourceABC:
    """The abstract base class cannot be instantiated directly."""

    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            HashSource()  # type: ignore[abstract]

    def test_subclass_must_implement_hashes(self):
        """A subclass that only implements name() is still abstract."""

        class Incomplete(HashSource):
            def name(self) -> str:
                return "incomplete"

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_subclass_must_implement_name(self):
        """A subclass that only implements hashes() is still abstract."""

        class Incomplete(HashSource):
            def hashes(self, count=None):
                yield from ()

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_complete_subclass_instantiates(self):
        """A subclass implementing both methods can be instantiated."""

        class Complete(HashSource):
            def hashes(self, count=None):
                yield from ()

            def name(self) -> str:
                return "complete"

        engine = Complete()
        assert engine.name() == "complete"


# -------------------------------------------------------------------
# SoftwareHashEngine
# -------------------------------------------------------------------

class TestSoftwareHashEngine:
    """Tests for the basic software SHA-256d engine."""

    def test_hashes_count_1_yields_exactly_1(self):
        engine = SoftwareHashEngine()
        results = list(engine.hashes(count=1))
        assert len(results) == 1

    def test_hashes_count_10_yields_exactly_10(self):
        engine = SoftwareHashEngine()
        results = list(engine.hashes(count=10))
        assert len(results) == 10

    def test_each_pair_is_tuple_of_bytes(self):
        engine = SoftwareHashEngine()
        for inp, out in engine.hashes(count=5):
            assert isinstance(inp, bytes)
            assert isinstance(out, bytes)

    def test_input_is_32_bytes(self):
        engine = SoftwareHashEngine()
        for inp, _ in engine.hashes(count=5):
            assert len(inp) == 32

    def test_output_is_32_bytes(self):
        engine = SoftwareHashEngine()
        for _, out in engine.hashes(count=5):
            assert len(out) == 32

    def test_output_matches_manual_sha256d(self):
        """Each output must equal SHA256(SHA256(input))."""
        engine = SoftwareHashEngine()
        for inp, out in engine.hashes(count=20):
            expected = hashlib.sha256(
                hashlib.sha256(inp).digest()
            ).digest()
            assert out == expected

    def test_count_none_produces_indefinitely(self):
        """count=None should produce an unbounded stream."""
        engine = SoftwareHashEngine()
        results = list(itertools.islice(engine.hashes(count=None), 5))
        assert len(results) == 5

    def test_start_0_and_start_100_produce_different_sequences(self):
        engine_a = SoftwareHashEngine(start=0)
        engine_b = SoftwareHashEngine(start=100)
        first_a = next(iter(engine_a.hashes(count=1)))
        first_b = next(iter(engine_b.hashes(count=1)))
        assert first_a != first_b

    def test_same_start_produces_same_sequence(self):
        """Determinism: identical start values yield identical output."""
        engine_a = SoftwareHashEngine(start=42)
        engine_b = SoftwareHashEngine(start=42)
        seq_a = list(engine_a.hashes(count=10))
        seq_b = list(engine_b.hashes(count=10))
        assert seq_a == seq_b

    def test_name_returns_correct_string(self):
        engine = SoftwareHashEngine()
        assert engine.name() == "software-sha256d"

    def test_consecutive_inputs_differ(self):
        """Consecutive inputs must not be identical."""
        engine = SoftwareHashEngine()
        pairs = list(engine.hashes(count=5))
        for i in range(len(pairs) - 1):
            assert pairs[i][0] != pairs[i + 1][0]

    def test_input_format_matches_spec(self):
        """Input should be struct.pack('>I', counter) left-justified to 32 bytes."""
        engine = SoftwareHashEngine(start=7)
        inp, _ = next(iter(engine.hashes(count=1)))
        expected = struct.pack(">I", 7).ljust(32, b"\x00")
        assert inp == expected

    def test_counter_increments(self):
        """The first 4 bytes should reflect the incrementing counter."""
        engine = SoftwareHashEngine(start=0)
        pairs = list(engine.hashes(count=5))
        for i, (inp, _) in enumerate(pairs):
            counter_val = struct.unpack(">I", inp[:4])[0]
            assert counter_val == i

    def test_is_instance_of_hash_source(self):
        engine = SoftwareHashEngine()
        assert isinstance(engine, HashSource)


# -------------------------------------------------------------------
# SequentialInputEngine
# -------------------------------------------------------------------

class TestSequentialInputEngine:
    """Tests for the sequential-input engine designed for avalanche analysis."""

    def test_hashes_count_1_yields_exactly_1(self):
        engine = SequentialInputEngine()
        results = list(engine.hashes(count=1))
        assert len(results) == 1

    def test_hashes_count_10_yields_exactly_10(self):
        engine = SequentialInputEngine()
        results = list(engine.hashes(count=10))
        assert len(results) == 10

    def test_each_pair_is_tuple_of_bytes(self):
        engine = SequentialInputEngine()
        for inp, out in engine.hashes(count=5):
            assert isinstance(inp, bytes)
            assert isinstance(out, bytes)

    def test_input_is_32_bytes(self):
        engine = SequentialInputEngine()
        for inp, _ in engine.hashes(count=5):
            assert len(inp) == 32

    def test_output_is_32_bytes(self):
        engine = SequentialInputEngine()
        for _, out in engine.hashes(count=5):
            assert len(out) == 32

    def test_output_matches_manual_sha256d(self):
        """Each output must equal SHA256(SHA256(input))."""
        engine = SequentialInputEngine()
        for inp, out in engine.hashes(count=20):
            expected = hashlib.sha256(
                hashlib.sha256(inp).digest()
            ).digest()
            assert out == expected

    def test_count_none_produces_indefinitely(self):
        engine = SequentialInputEngine()
        results = list(itertools.islice(engine.hashes(count=None), 5))
        assert len(results) == 5

    def test_consecutive_inputs_differ_by_exactly_1_in_last_8_bytes(self):
        """Consecutive inputs differ by exactly +1 in the last 8 bytes."""
        engine = SequentialInputEngine()
        pairs = list(engine.hashes(count=10))
        for i in range(len(pairs) - 1):
            inp_a = pairs[i][0]
            inp_b = pairs[i + 1][0]
            # Prefixes (first 24 bytes) must be identical
            assert inp_a[:24] == inp_b[:24]
            # Last 8 bytes must differ by exactly 1
            val_a = struct.unpack(">Q", inp_a[24:])[0]
            val_b = struct.unpack(">Q", inp_b[24:])[0]
            assert val_b - val_a == 1

    def test_default_base_is_24_zero_bytes(self):
        engine = SequentialInputEngine()
        inp, _ = next(iter(engine.hashes(count=1)))
        assert inp[:24] == b"\x00" * 24

    def test_custom_base_is_preserved_in_input_prefix(self):
        base = bytes(range(24))
        engine = SequentialInputEngine(base=base)
        for inp, _ in engine.hashes(count=5):
            assert inp[:24] == base

    def test_base_validation_too_short(self):
        with pytest.raises(ValueError, match="24 bytes"):
            SequentialInputEngine(base=b"\x00" * 23)

    def test_base_validation_too_long(self):
        with pytest.raises(ValueError, match="24 bytes"):
            SequentialInputEngine(base=b"\x00" * 25)

    def test_base_validation_empty(self):
        with pytest.raises(ValueError, match="24 bytes"):
            SequentialInputEngine(base=b"")

    def test_base_none_is_accepted(self):
        """None should be accepted and default to zeros."""
        engine = SequentialInputEngine(base=None)
        inp, _ = next(iter(engine.hashes(count=1)))
        assert inp[:24] == b"\x00" * 24

    def test_name_returns_correct_string(self):
        engine = SequentialInputEngine()
        assert engine.name() == "sequential-input-sha256d"

    def test_start_0_and_start_100_produce_different_sequences(self):
        engine_a = SequentialInputEngine(start=0)
        engine_b = SequentialInputEngine(start=100)
        first_a = next(iter(engine_a.hashes(count=1)))
        first_b = next(iter(engine_b.hashes(count=1)))
        assert first_a != first_b

    def test_same_start_produces_same_sequence(self):
        engine_a = SequentialInputEngine(start=42)
        engine_b = SequentialInputEngine(start=42)
        seq_a = list(engine_a.hashes(count=10))
        seq_b = list(engine_b.hashes(count=10))
        assert seq_a == seq_b

    def test_is_instance_of_hash_source(self):
        engine = SequentialInputEngine()
        assert isinstance(engine, HashSource)

    def test_counter_in_last_8_bytes(self):
        """The last 8 bytes encode the counter as big-endian uint64."""
        engine = SequentialInputEngine(start=7)
        inp, _ = next(iter(engine.hashes(count=1)))
        counter_val = struct.unpack(">Q", inp[24:])[0]
        assert counter_val == 7

    def test_consecutive_inputs_differ(self):
        """Consecutive inputs must not be identical."""
        engine = SequentialInputEngine()
        pairs = list(engine.hashes(count=5))
        for i in range(len(pairs) - 1):
            assert pairs[i][0] != pairs[i + 1][0]
