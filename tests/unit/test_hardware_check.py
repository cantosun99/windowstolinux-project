"""Unit tests for windowstolinux.matcher.hardware_check."""

from __future__ import annotations

import json

import pytest

from windowstolinux.matcher.hardware_check import (
    DISK_RED_GB,
    DISK_YELLOW_GB,
    RAM_RED_GB,
    RAM_YELLOW_GB,
    _check_blacklist,
    _check_cpu,
    _check_disk,
    _check_ram,
    _get_boot_key_hint,
    _load_blacklist,
    _overall_status,
    check_hardware,
)
from windowstolinux.models import HardwareInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hw(
    *,
    cpu_64bit: bool = True,
    cpu_cores: int = 4,
    cpu_name: str = "Intel Core i5",
    ram_gb: float = 8.0,
    disk_free_gb: float = 60.0,
    gpu_name: str | None = None,
    wlan_chipset: str | None = None,
    manufacturer: str | None = None,
    model: str | None = None,
) -> HardwareInfo:
    return HardwareInfo(
        cpu_64bit=cpu_64bit,
        cpu_cores=cpu_cores,
        cpu_name=cpu_name,
        ram_gb=ram_gb,
        disk_free_gb=disk_free_gb,
        gpu_name=gpu_name,
        wlan_chipset=wlan_chipset,
        manufacturer=manufacturer,
        model=model,
    )


# ---------------------------------------------------------------------------
# _overall_status
# ---------------------------------------------------------------------------


def test_overall_all_green() -> None:
    assert _overall_status("green", "green", "green") == "green"


def test_overall_one_yellow() -> None:
    assert _overall_status("green", "yellow", "green") == "yellow"


def test_overall_one_red() -> None:
    assert _overall_status("green", "yellow", "red") == "red"


def test_overall_all_red() -> None:
    assert _overall_status("red", "red", "red") == "red"


def test_overall_red_beats_yellow() -> None:
    assert _overall_status("red", "yellow") == "red"


# ---------------------------------------------------------------------------
# _check_cpu
# ---------------------------------------------------------------------------


def test_check_cpu_64bit_is_green() -> None:
    status, issues = _check_cpu(_hw(cpu_64bit=True))
    assert status == "green"
    assert issues == []


def test_check_cpu_32bit_is_red() -> None:
    status, issues = _check_cpu(_hw(cpu_64bit=False))
    assert status == "red"
    assert len(issues) == 1
    assert "32-Bit" in issues[0]
    assert "64-Bit" in issues[0]


# ---------------------------------------------------------------------------
# _check_ram
# ---------------------------------------------------------------------------


def test_check_ram_above_recommended_is_green() -> None:
    status, issues = _check_ram(RAM_YELLOW_GB)
    assert status == "green"
    assert issues == []


def test_check_ram_well_above_recommended() -> None:
    status, issues = _check_ram(16.0)
    assert status == "green"
    assert issues == []


def test_check_ram_between_min_and_recommended_is_yellow() -> None:
    status, issues = _check_ram(RAM_RED_GB)
    assert status == "yellow"
    assert len(issues) == 1
    assert str(int(RAM_YELLOW_GB)) in issues[0]


def test_check_ram_just_below_recommended() -> None:
    status, issues = _check_ram(RAM_YELLOW_GB - 0.1)
    assert status == "yellow"


def test_check_ram_below_minimum_is_red() -> None:
    status, issues = _check_ram(RAM_RED_GB - 0.1)
    assert status == "red"
    assert len(issues) == 1
    assert str(int(RAM_RED_GB)) in issues[0]


def test_check_ram_zero_is_red() -> None:
    status, _ = _check_ram(0.0)
    assert status == "red"


def test_check_ram_issue_contains_actual_value() -> None:
    _, issues = _check_ram(1.5)
    assert "1.5" in issues[0]


# ---------------------------------------------------------------------------
# _check_disk
# ---------------------------------------------------------------------------


def test_check_disk_above_recommended_is_green() -> None:
    status, issues = _check_disk(DISK_YELLOW_GB)
    assert status == "green"
    assert issues == []


def test_check_disk_well_above_recommended() -> None:
    status, _ = _check_disk(200.0)
    assert status == "green"


def test_check_disk_between_min_and_recommended_is_yellow() -> None:
    status, issues = _check_disk(DISK_RED_GB)
    assert status == "yellow"
    assert len(issues) == 1
    assert str(int(DISK_YELLOW_GB)) in issues[0]


def test_check_disk_just_below_recommended() -> None:
    status, _ = _check_disk(DISK_YELLOW_GB - 0.1)
    assert status == "yellow"


def test_check_disk_below_minimum_is_red() -> None:
    status, issues = _check_disk(DISK_RED_GB - 0.1)
    assert status == "red"
    assert len(issues) == 1
    assert str(int(DISK_RED_GB)) in issues[0]


def test_check_disk_issue_contains_actual_value() -> None:
    _, issues = _check_disk(10.0)
    assert "10" in issues[0]


# ---------------------------------------------------------------------------
# _get_boot_key_hint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("manufacturer, expected_key", [
    ("Lenovo", "F12"),
    ("LENOVO", "F12"),
    ("Lenovo Group Limited", "F12"),
    ("Dell Inc.", "F12"),
    ("DELL", "F12"),
    ("HP", "F9"),
    ("Hewlett-Packard", "F9"),
    ("Acer", "F12"),
    ("ASUSTeK COMPUTER INC.", "F8"),
    ("MSI", "F11"),
    ("Samsung Electronics", "F2"),
    ("TOSHIBA", "F12"),
    ("Sony Corporation", "F11"),
    ("FUJITSU", "F12"),
    ("Gigabyte Technology", "F12"),
])
def test_get_boot_key_known_manufacturers(manufacturer: str, expected_key: str) -> None:
    assert _get_boot_key_hint(manufacturer) == expected_key


def test_get_boot_key_unknown_manufacturer() -> None:
    assert _get_boot_key_hint("Acme Computers Inc.") is None


def test_get_boot_key_none_manufacturer() -> None:
    assert _get_boot_key_hint(None) is None


def test_get_boot_key_empty_string() -> None:
    assert _get_boot_key_hint("") is None


# ---------------------------------------------------------------------------
# _load_blacklist
# ---------------------------------------------------------------------------


def test_load_blacklist_returns_dict(tmp_path, monkeypatch) -> None:
    bl = {"gpu_substrings": ["Radeon HD"], "wlan_substrings": ["Broadcom BCM43"]}
    bl_file = tmp_path / "hardware_blacklist.json"
    bl_file.write_text(json.dumps(bl), encoding="utf-8")

    import windowstolinux.matcher.hardware_check as hc
    monkeypatch.setattr(hc, "_BLACKLIST_PATH", bl_file)

    result = _load_blacklist()
    assert result["gpu_substrings"] == ["Radeon HD"]
    assert result["wlan_substrings"] == ["Broadcom BCM43"]


def test_load_blacklist_missing_file_returns_empty(tmp_path, monkeypatch) -> None:
    import windowstolinux.matcher.hardware_check as hc
    monkeypatch.setattr(hc, "_BLACKLIST_PATH", tmp_path / "nonexistent.json")

    result = _load_blacklist()
    assert result == {"gpu_substrings": [], "wlan_substrings": []}


def test_load_blacklist_invalid_json_returns_empty(tmp_path, monkeypatch) -> None:
    bl_file = tmp_path / "hardware_blacklist.json"
    bl_file.write_text("{ not valid json", encoding="utf-8")

    import windowstolinux.matcher.hardware_check as hc
    monkeypatch.setattr(hc, "_BLACKLIST_PATH", bl_file)

    result = _load_blacklist()
    assert result == {"gpu_substrings": [], "wlan_substrings": []}


# ---------------------------------------------------------------------------
# _check_blacklist
# ---------------------------------------------------------------------------


def test_check_blacklist_no_match_when_empty_blacklist(monkeypatch) -> None:
    import windowstolinux.matcher.hardware_check as hc
    monkeypatch.setattr(hc, "_load_blacklist", lambda: {"gpu_substrings": [], "wlan_substrings": []})

    hw = _hw(gpu_name="NVIDIA RTX 4090", wlan_chipset="Intel AX210")
    assert _check_blacklist(hw) == []


def test_check_blacklist_gpu_match(monkeypatch) -> None:
    import windowstolinux.matcher.hardware_check as hc
    monkeypatch.setattr(hc, "_load_blacklist", lambda: {
        "gpu_substrings": ["Radeon HD 4000"],
        "wlan_substrings": [],
    })

    hw = _hw(gpu_name="AMD Radeon HD 4000 Series")
    issues = _check_blacklist(hw)
    assert len(issues) == 1
    assert "Radeon HD 4000 Series" in issues[0]


def test_check_blacklist_wlan_match(monkeypatch) -> None:
    import windowstolinux.matcher.hardware_check as hc
    monkeypatch.setattr(hc, "_load_blacklist", lambda: {
        "gpu_substrings": [],
        "wlan_substrings": ["BCM4311"],
    })

    hw = _hw(wlan_chipset="Broadcom BCM4311")
    issues = _check_blacklist(hw)
    assert len(issues) == 1
    assert "BCM4311" in issues[0]


def test_check_blacklist_case_insensitive(monkeypatch) -> None:
    import windowstolinux.matcher.hardware_check as hc
    monkeypatch.setattr(hc, "_load_blacklist", lambda: {
        "gpu_substrings": ["radeon hd 4000"],
        "wlan_substrings": [],
    })

    hw = _hw(gpu_name="AMD RADEON HD 4000 SERIES")
    issues = _check_blacklist(hw)
    assert len(issues) == 1


def test_check_blacklist_no_gpu_or_wlan_no_crash(monkeypatch) -> None:
    import windowstolinux.matcher.hardware_check as hc
    monkeypatch.setattr(hc, "_load_blacklist", lambda: {
        "gpu_substrings": ["anything"],
        "wlan_substrings": ["anything"],
    })

    hw = _hw(gpu_name=None, wlan_chipset=None)
    assert _check_blacklist(hw) == []


# ---------------------------------------------------------------------------
# check_hardware (integration)
# ---------------------------------------------------------------------------


def test_check_hardware_all_green() -> None:
    hw = _hw(cpu_64bit=True, ram_gb=8.0, disk_free_gb=60.0, manufacturer="Lenovo")
    verdict = check_hardware(hw)
    assert verdict.overall == "green"
    assert verdict.cpu_status == "green"
    assert verdict.ram_status == "green"
    assert verdict.disk_status == "green"
    assert verdict.issues == []
    assert verdict.boot_key_hint == "F12"


def test_check_hardware_32bit_cpu_is_red() -> None:
    hw = _hw(cpu_64bit=False, ram_gb=8.0, disk_free_gb=60.0)
    verdict = check_hardware(hw)
    assert verdict.overall == "red"
    assert verdict.cpu_status == "red"
    assert len(verdict.issues) == 1


def test_check_hardware_low_ram_is_yellow() -> None:
    hw = _hw(ram_gb=3.0, disk_free_gb=60.0)
    verdict = check_hardware(hw)
    assert verdict.overall == "yellow"
    assert verdict.ram_status == "yellow"
    assert verdict.cpu_status == "green"
    assert verdict.disk_status == "green"


def test_check_hardware_very_low_ram_is_red() -> None:
    hw = _hw(ram_gb=1.0, disk_free_gb=60.0)
    verdict = check_hardware(hw)
    assert verdict.overall == "red"
    assert verdict.ram_status == "red"


def test_check_hardware_low_disk_is_yellow() -> None:
    hw = _hw(disk_free_gb=25.0)
    verdict = check_hardware(hw)
    assert verdict.overall == "yellow"
    assert verdict.disk_status == "yellow"


def test_check_hardware_very_low_disk_is_red() -> None:
    hw = _hw(disk_free_gb=10.0)
    verdict = check_hardware(hw)
    assert verdict.overall == "red"
    assert verdict.disk_status == "red"


def test_check_hardware_multiple_issues_accumulated() -> None:
    hw = _hw(cpu_64bit=True, ram_gb=1.0, disk_free_gb=10.0)
    verdict = check_hardware(hw)
    assert verdict.overall == "red"
    assert len(verdict.issues) == 2  # RAM red + disk red


def test_check_hardware_red_beats_yellow_for_overall() -> None:
    # RAM is yellow, disk is red
    hw = _hw(ram_gb=3.0, disk_free_gb=10.0)
    verdict = check_hardware(hw)
    assert verdict.overall == "red"
    assert verdict.ram_status == "yellow"
    assert verdict.disk_status == "red"


def test_check_hardware_blacklist_issue_makes_green_yellow(monkeypatch) -> None:
    import windowstolinux.matcher.hardware_check as hc
    monkeypatch.setattr(hc, "_load_blacklist", lambda: {
        "gpu_substrings": ["Radeon HD 4000"],
        "wlan_substrings": [],
    })

    hw = _hw(ram_gb=8.0, disk_free_gb=60.0, gpu_name="AMD Radeon HD 4000 Series")
    verdict = check_hardware(hw)
    assert verdict.overall == "yellow"
    assert len(verdict.issues) == 1


def test_check_hardware_no_manufacturer_no_boot_hint() -> None:
    verdict = check_hardware(_hw())
    assert verdict.boot_key_hint is None


def test_check_hardware_unknown_manufacturer_no_boot_hint() -> None:
    verdict = check_hardware(_hw(manufacturer="Acme Corp"))
    assert verdict.boot_key_hint is None
