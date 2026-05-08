"""Unit tests for windowstolinux.scanner.hardware."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from windowstolinux.scanner.hardware import (
    _get_disk_free_gb,
    _query_wmi,
    _wmi_cpu_name,
    _wmi_gpu_name,
    _wmi_system_info,
    _wmi_wlan_chipset,
    scan_hardware,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WMI_RESULT = ("Intel Core i5-12400", "NVIDIA RTX 3060", "Intel AX210", "Lenovo", "ThinkPad X1")


def _mock_psutil(mocker, *, cores: int = 4, ram_bytes: int = 8 * 1024**3, disk_free: int = 100 * 1024**3) -> None:
    mocker.patch("windowstolinux.scanner.hardware.psutil.cpu_count", return_value=cores)
    vm = MagicMock()
    vm.total = ram_bytes
    mocker.patch("windowstolinux.scanner.hardware.psutil.virtual_memory", return_value=vm)
    du = MagicMock()
    du.free = disk_free
    mocker.patch("windowstolinux.scanner.hardware.psutil.disk_usage", return_value=du)


# ---------------------------------------------------------------------------
# scan_hardware
# ---------------------------------------------------------------------------


def test_scan_hardware_64bit(mocker) -> None:
    mocker.patch("windowstolinux.scanner.hardware.platform.machine", return_value="AMD64")
    _mock_psutil(mocker)
    mocker.patch("windowstolinux.scanner.hardware._query_wmi", return_value=_WMI_RESULT)

    hw = scan_hardware()

    assert hw.cpu_64bit is True
    assert hw.cpu_name == "Intel Core i5-12400"
    assert hw.cpu_cores == 4
    assert hw.ram_gb == pytest.approx(8.0, abs=0.1)
    assert hw.disk_free_gb == pytest.approx(100.0, abs=0.1)
    assert hw.gpu_name == "NVIDIA RTX 3060"
    assert hw.wlan_chipset == "Intel AX210"
    assert hw.manufacturer == "Lenovo"
    assert hw.model == "ThinkPad X1"


def test_scan_hardware_32bit(mocker) -> None:
    mocker.patch("windowstolinux.scanner.hardware.platform.machine", return_value="x86")
    _mock_psutil(mocker)
    mocker.patch("windowstolinux.scanner.hardware._query_wmi", return_value=_WMI_RESULT)

    hw = scan_hardware()

    assert hw.cpu_64bit is False


def test_scan_hardware_wmi_unavailable(mocker) -> None:
    mocker.patch("windowstolinux.scanner.hardware.platform.machine", return_value="AMD64")
    _mock_psutil(mocker)
    # _query_wmi falls back gracefully: only cpu_name set, rest None
    mocker.patch(
        "windowstolinux.scanner.hardware._query_wmi",
        return_value=("GenuineIntel", None, None, None, None),
    )

    hw = scan_hardware()

    assert hw.cpu_name == "GenuineIntel"
    assert hw.gpu_name is None
    assert hw.manufacturer is None


def test_scan_hardware_single_core_fallback(mocker) -> None:
    """psutil.cpu_count can return None on some systems - should default to 1."""
    mocker.patch("windowstolinux.scanner.hardware.platform.machine", return_value="AMD64")
    _mock_psutil(mocker, cores=None)  # type: ignore[arg-type]
    mocker.patch("windowstolinux.scanner.hardware._query_wmi", return_value=_WMI_RESULT)

    hw = scan_hardware()

    assert hw.cpu_cores == 1


def test_scan_hardware_ram_rounded(mocker) -> None:
    mocker.patch("windowstolinux.scanner.hardware.platform.machine", return_value="AMD64")
    # 6 GB exactly
    _mock_psutil(mocker, ram_bytes=6 * 1024**3)
    mocker.patch("windowstolinux.scanner.hardware._query_wmi", return_value=_WMI_RESULT)

    hw = scan_hardware()

    assert hw.ram_gb == 6.0


# ---------------------------------------------------------------------------
# _get_disk_free_gb
# ---------------------------------------------------------------------------


def test_get_disk_free_gb_uses_system_drive(mocker) -> None:
    mocker.patch.dict("os.environ", {"SystemDrive": "D:"})
    du = MagicMock()
    du.free = 50 * 1024**3
    mock_du = mocker.patch("windowstolinux.scanner.hardware.psutil.disk_usage", return_value=du)

    result = _get_disk_free_gb()

    mock_du.assert_called_once_with("D:\\")
    assert result == pytest.approx(50.0, abs=0.1)


def test_get_disk_free_gb_default_c_drive(mocker) -> None:
    mocker.patch.dict("os.environ", {}, clear=True)  # no SystemDrive set
    du = MagicMock()
    du.free = 200 * 1024**3
    mock_du = mocker.patch("windowstolinux.scanner.hardware.psutil.disk_usage", return_value=du)

    _get_disk_free_gb()

    mock_du.assert_called_once_with("C:\\")


# ---------------------------------------------------------------------------
# _query_wmi (integration-level: mocks the wmi library itself)
# ---------------------------------------------------------------------------


def _make_wmi_mock(
    cpu_name: str = "Intel Core i5",
    gpu_name: str = "NVIDIA RTX 3060",
    adapter_type: str = "Wireless",
    adapter_name: str = "Intel AX210",
    manufacturer: str = "Lenovo",
    model: str = "ThinkPad X1",
) -> MagicMock:
    """Build a mock wmi.WMI() instance with realistic query results."""
    c = MagicMock()

    proc = MagicMock()
    proc.Name = cpu_name
    c.Win32_Processor.return_value = [proc]

    gpu = MagicMock()
    gpu.Name = gpu_name
    c.Win32_VideoController.return_value = [gpu]

    nic = MagicMock()
    nic.AdapterType = adapter_type
    nic.Name = adapter_name
    c.Win32_NetworkAdapter.return_value = [nic]

    sys = MagicMock()
    sys.Manufacturer = manufacturer
    sys.Model = model
    c.Win32_ComputerSystem.return_value = [sys]

    return c


def test_query_wmi_success(mocker) -> None:
    wmi_mod = MagicMock()
    wmi_mod.WMI.return_value = _make_wmi_mock()
    mocker.patch.dict("sys.modules", {"wmi": wmi_mod})

    cpu, gpu, wlan, mfr, mdl = _query_wmi()

    assert cpu == "Intel Core i5"
    assert gpu == "NVIDIA RTX 3060"
    assert wlan == "Intel AX210"
    assert mfr == "Lenovo"
    assert mdl == "ThinkPad X1"


def test_query_wmi_import_error(mocker) -> None:
    mocker.patch("builtins.__import__", side_effect=ImportError("No module named 'wmi'"))
    mocker.patch("windowstolinux.scanner.hardware.platform.processor", return_value="GenuineIntel")

    cpu, gpu, wlan, mfr, mdl = _query_wmi()

    assert cpu == "GenuineIntel"
    assert gpu is None
    assert wlan is None
    assert mfr is None
    assert mdl is None


def test_query_wmi_exception_fallback(mocker) -> None:
    wmi_mod = MagicMock()
    wmi_mod.WMI.side_effect = Exception("COM error")
    mocker.patch.dict("sys.modules", {"wmi": wmi_mod})
    mocker.patch("windowstolinux.scanner.hardware.platform.processor", return_value="x86_64")

    cpu, gpu, wlan, mfr, mdl = _query_wmi()

    assert cpu == "x86_64"
    assert all(v is None for v in (gpu, wlan, mfr, mdl))


# ---------------------------------------------------------------------------
# WMI sub-functions
# ---------------------------------------------------------------------------


def test_wmi_cpu_name_strips_whitespace() -> None:
    c = MagicMock()
    proc = MagicMock()
    proc.Name = "  Intel Core i7-13700K  "
    c.Win32_Processor.return_value = [proc]

    assert _wmi_cpu_name(c) == "Intel Core i7-13700K"


def test_wmi_cpu_name_empty_list() -> None:
    c = MagicMock()
    c.Win32_Processor.return_value = []

    assert _wmi_cpu_name(c) == "Unbekannt"


def test_wmi_gpu_skips_microsoft_adapter() -> None:
    c = MagicMock()
    ms_gpu = MagicMock()
    ms_gpu.Name = "Microsoft Basic Display Adapter"
    real_gpu = MagicMock()
    real_gpu.Name = "AMD Radeon RX 6700"
    c.Win32_VideoController.return_value = [ms_gpu, real_gpu]

    assert _wmi_gpu_name(c) == "AMD Radeon RX 6700"


def test_wmi_gpu_none_when_only_microsoft() -> None:
    c = MagicMock()
    gpu = MagicMock()
    gpu.Name = "Microsoft Basic Display Adapter"
    c.Win32_VideoController.return_value = [gpu]

    assert _wmi_gpu_name(c) is None


def test_wmi_gpu_none_when_empty() -> None:
    c = MagicMock()
    c.Win32_VideoController.return_value = []

    assert _wmi_gpu_name(c) is None


def test_wmi_wlan_chipset_wireless_type() -> None:
    c = MagicMock()
    nic = MagicMock()
    nic.AdapterType = "Wireless"
    nic.Name = "Intel Wi-Fi 6 AX200"
    c.Win32_NetworkAdapter.return_value = [nic]

    assert _wmi_wlan_chipset(c) == "Intel Wi-Fi 6 AX200"


def test_wmi_wlan_chipset_802_11_type() -> None:
    c = MagicMock()
    nic = MagicMock()
    nic.AdapterType = "802.11 Wireless"
    nic.Name = "Realtek RTL8822CE"
    c.Win32_NetworkAdapter.return_value = [nic]

    assert _wmi_wlan_chipset(c) == "Realtek RTL8822CE"


def test_wmi_wlan_chipset_none_when_no_wireless() -> None:
    c = MagicMock()
    nic = MagicMock()
    nic.AdapterType = "Ethernet 802.3"
    nic.Name = "Intel I225-V"
    c.Win32_NetworkAdapter.return_value = [nic]

    assert _wmi_wlan_chipset(c) is None


def test_wmi_system_info_none_when_empty() -> None:
    c = MagicMock()
    c.Win32_ComputerSystem.return_value = []

    mfr, mdl = _wmi_system_info(c)

    assert mfr is None
    assert mdl is None


def test_wmi_system_info_strips_whitespace() -> None:
    c = MagicMock()
    sys = MagicMock()
    sys.Manufacturer = "  Dell Inc.  "
    sys.Model = "  XPS 15 9530  "
    c.Win32_ComputerSystem.return_value = [sys]

    mfr, mdl = _wmi_system_info(c)

    assert mfr == "Dell Inc."
    assert mdl == "XPS 15 9530"
