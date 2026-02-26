"""Tests for the asynchronous AsyncBFLDevice API against SimulatorTransport."""

from __future__ import annotations

import pytest

from bfl_asic.async_device import AsyncBFLDevice
from bfl_asic.protocol.responses import (
    DeviceInfo,
    TemperatureReading,
    WorkResult,
    WorkStatus,
)
from bfl_asic.protocol.work import build_synthetic_work
from bfl_asic.transport.simulator import SimulatorTransport


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def async_device():
    """Provide an AsyncBFLDevice backed by an opened SimulatorTransport."""
    transport = SimulatorTransport()
    transport.open()
    yield AsyncBFLDevice(transport)
    transport.close()


# ======================================================================
# Identify
# ======================================================================


class TestAsyncIdentify:
    async def test_identify_returns_device_info(self, async_device: AsyncBFLDevice):
        info = await async_device.identify()
        assert isinstance(info, DeviceInfo)

    async def test_identify_sha256_flag(self, async_device: AsyncBFLDevice):
        info = await async_device.identify()
        assert info.sha256 is True

    async def test_identify_model_string(self, async_device: AsyncBFLDevice):
        info = await async_device.identify()
        assert "Jalapeno" in info.model


# ======================================================================
# Temperature
# ======================================================================


class TestAsyncGetTemperature:
    async def test_returns_temperature_reading(self, async_device: AsyncBFLDevice):
        reading = await async_device.get_temperature()
        assert isinstance(reading, TemperatureReading)

    async def test_has_sensor_values(self, async_device: AsyncBFLDevice):
        reading = await async_device.get_temperature()
        assert len(reading.sensors) >= 1

    async def test_sensor_value_reasonable(self, async_device: AsyncBFLDevice):
        reading = await async_device.get_temperature()
        assert 0.0 < reading.sensors[0] < 150.0


# ======================================================================
# Submit and wait
# ======================================================================


class TestAsyncSubmitAndWait:
    async def test_returns_work_result(self, async_device: AsyncBFLDevice):
        midstate, tail = build_synthetic_work(b"\x00" * 64)
        result = await async_device.submit_and_wait(midstate, tail)
        assert isinstance(result, WorkResult)

    async def test_result_not_busy(self, async_device: AsyncBFLDevice):
        midstate, tail = build_synthetic_work(b"\x00" * 64)
        result = await async_device.submit_and_wait(midstate, tail)
        assert result.status != WorkStatus.BUSY

    async def test_result_is_nonce_found_or_no_nonce(
        self, async_device: AsyncBFLDevice
    ):
        midstate, tail = build_synthetic_work(b"\x00" * 64)
        result = await async_device.submit_and_wait(midstate, tail)
        assert result.status in (WorkStatus.NONCE_FOUND, WorkStatus.NO_NONCE)

    async def test_nonces_are_ints(self, async_device: AsyncBFLDevice):
        midstate, tail = build_synthetic_work(b"\x01" * 64)
        result = await async_device.submit_and_wait(midstate, tail)
        for nonce in result.nonces:
            assert isinstance(nonce, int)


# ======================================================================
# hash_stream
# ======================================================================


class TestAsyncHashStream:
    async def test_yields_work_results(self, async_device: AsyncBFLDevice):
        results = []
        async for result in async_device.hash_stream(count=3):
            results.append(result)
        assert len(results) == 3

    async def test_each_result_is_work_result(self, async_device: AsyncBFLDevice):
        async for result in async_device.hash_stream(count=2):
            assert isinstance(result, WorkResult)

    async def test_results_not_busy(self, async_device: AsyncBFLDevice):
        async for result in async_device.hash_stream(count=2):
            assert result.status != WorkStatus.BUSY

    async def test_count_one(self, async_device: AsyncBFLDevice):
        results = []
        async for result in async_device.hash_stream(count=1):
            results.append(result)
        assert len(results) == 1


# ======================================================================
# entropy_stream
# ======================================================================


class TestAsyncEntropyStream:
    async def test_yields_bytes(self, async_device: AsyncBFLDevice):
        chunks = []
        async for chunk in async_device.entropy_stream(chunk_size=16):
            chunks.append(chunk)
            if len(chunks) >= 2:
                break
        assert len(chunks) == 2

    async def test_chunk_size(self, async_device: AsyncBFLDevice):
        async for chunk in async_device.entropy_stream(chunk_size=16):
            assert len(chunk) == 16
            break  # Just check the first chunk

    async def test_different_chunk_sizes(self, async_device: AsyncBFLDevice):
        for size in (4, 8, 32):
            async for chunk in async_device.entropy_stream(chunk_size=size):
                assert len(chunk) == size
                break

    async def test_entropy_is_bytes(self, async_device: AsyncBFLDevice):
        async for chunk in async_device.entropy_stream(chunk_size=8):
            assert isinstance(chunk, bytes)
            break


# ======================================================================
# Async context manager
# ======================================================================


class TestAsyncContextManager:
    async def test_opens_and_closes_transport(self):
        transport = SimulatorTransport()
        assert transport.is_open is False
        async with AsyncBFLDevice(transport) as dev:
            assert transport.is_open is True
            info = await dev.identify()
            assert isinstance(info, DeviceInfo)
        assert transport.is_open is False

    async def test_closes_on_exception(self):
        transport = SimulatorTransport()
        with pytest.raises(RuntimeError):
            async with AsyncBFLDevice(transport):
                assert transport.is_open is True
                raise RuntimeError("test")
        assert transport.is_open is False


# ======================================================================
# Transport property
# ======================================================================


class TestAsyncTransportProperty:
    async def test_access_transport(self, async_device: AsyncBFLDevice):
        assert isinstance(async_device.transport, SimulatorTransport)

    async def test_transport_is_open(self, async_device: AsyncBFLDevice):
        assert async_device.transport.is_open is True


# ======================================================================
# Package-level import
# ======================================================================


class TestAsyncPackageExport:
    def test_importable_from_package(self):
        from bfl_asic import AsyncBFLDevice as Imported
        assert Imported is AsyncBFLDevice
