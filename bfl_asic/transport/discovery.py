"""Cross-platform detection of BFL FTDI USB serial devices.

Scans the host's serial ports for FTDI chips (vendor ID ``0x0403``) and
for any device whose description contains BFL-related keywords.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DevicePort:
    """Information about a detected serial device."""

    port: str  #: e.g. ``'/dev/ttyUSB0'`` or ``'COM3'``
    description: str  #: Human-readable device description
    vid: int | None  #: USB Vendor ID (``0x0403`` for FTDI)
    pid: int | None  #: USB Product ID


#: FTDI vendor ID used for matching.
FTDI_VID: int = 0x0403


def discover_devices() -> list[DevicePort]:
    """Scan for potential BFL ASIC devices.

    Looks for FTDI USB serial devices (vendor ID ``0x0403``) and any
    devices with *Butterfly*, *BitFORCE*, or *BFL* in their description.

    Returns:
        A list of :class:`DevicePort` instances for all matching devices.
        Works on both Linux and Windows.
    """
    import serial.tools.list_ports

    results: list[DevicePort] = []
    for port_info in serial.tools.list_ports.comports():
        is_ftdi = port_info.vid == FTDI_VID
        is_bfl = any(
            keyword in (port_info.description or "").lower()
            for keyword in ("butterfly", "bitforce", "bfl")
        )

        if is_ftdi or is_bfl:
            results.append(
                DevicePort(
                    port=port_info.device,
                    description=port_info.description or "",
                    vid=port_info.vid,
                    pid=port_info.pid,
                )
            )

    return results
