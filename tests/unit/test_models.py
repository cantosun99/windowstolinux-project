"""Unit tests for windowstolinux.models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from windowstolinux.models import AppMatch, HardwareInfo, HardwareVerdict, Report, WindowsApp


# ---------------------------------------------------------------------------
# HardwareInfo
# ---------------------------------------------------------------------------


def test_hardware_info_minimal() -> None:
    hw = HardwareInfo(
        cpu_64bit=True,
        cpu_cores=4,
        cpu_name="Intel Core i5",
        ram_gb=8.0,
        disk_free_gb=50.0,
    )
    assert hw.gpu_name is None
    assert hw.wlan_chipset is None
    assert hw.manufacturer is None
    assert hw.model is None


def test_hardware_info_full() -> None:
    hw = HardwareInfo(
        cpu_64bit=True,
        cpu_cores=8,
        cpu_name="AMD Ryzen 7",
        ram_gb=16.0,
        disk_free_gb=200.0,
        gpu_name="NVIDIA RTX 3060",
        wlan_chipset="Intel AX210",
        manufacturer="Lenovo",
        model="ThinkPad X1 Carbon",
    )
    assert hw.manufacturer == "Lenovo"
    assert hw.wlan_chipset == "Intel AX210"


# ---------------------------------------------------------------------------
# HardwareVerdict
# ---------------------------------------------------------------------------


def test_hardware_verdict_defaults() -> None:
    v = HardwareVerdict(overall="green", cpu_status="green", ram_status="green", disk_status="green")
    assert v.issues == []
    assert v.boot_key_hint is None


def test_hardware_verdict_with_issues() -> None:
    v = HardwareVerdict(
        overall="yellow",
        cpu_status="green",
        ram_status="yellow",
        disk_status="green",
        issues=["RAM unter 4 GB empfohlen"],
        boot_key_hint="F12",
    )
    assert len(v.issues) == 1
    assert v.boot_key_hint == "F12"


def test_hardware_verdict_invalid_status() -> None:
    with pytest.raises(ValidationError):
        HardwareVerdict(overall="blue", cpu_status="green", ram_status="green", disk_status="green")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# WindowsApp
# ---------------------------------------------------------------------------


def test_windows_app_minimal() -> None:
    app = WindowsApp(name="VLC media player")
    assert app.publisher is None
    assert app.version is None


def test_windows_app_full() -> None:
    app = WindowsApp(name="VLC media player", publisher="VideoLAN", version="3.0.20")
    assert app.version == "3.0.20"


# ---------------------------------------------------------------------------
# AppMatch
# ---------------------------------------------------------------------------


def test_app_match_green() -> None:
    match = AppMatch(
        windows_app=WindowsApp(name="VLC media player"),
        category="green",
        linux_package="vlc",
        install_via="apt",
    )
    assert match.category == "green"
    assert match.linux_package == "vlc"


def test_app_match_red_no_package() -> None:
    match = AppMatch(
        windows_app=WindowsApp(name="Adobe Premiere"),
        category="red",
    )
    assert match.linux_package is None
    assert match.install_via is None


def test_app_match_package_without_via_raises() -> None:
    with pytest.raises(ValidationError, match="both be set or both be None"):
        AppMatch(
            windows_app=WindowsApp(name="SomeApp"),
            category="green",
            linux_package="some-pkg",
            # install_via missing
        )


def test_app_match_via_without_package_raises() -> None:
    with pytest.raises(ValidationError, match="both be set or both be None"):
        AppMatch(
            windows_app=WindowsApp(name="SomeApp"),
            category="green",
            install_via="apt",
            # linux_package missing
        )


def test_app_match_flatpak() -> None:
    match = AppMatch(
        windows_app=WindowsApp(name="GIMP"),
        category="green",
        linux_package="org.gimp.GIMP",
        install_via="flatpak",
    )
    assert match.install_via == "flatpak"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _make_report(**kwargs) -> Report:
    hw = HardwareInfo(cpu_64bit=True, cpu_cores=4, cpu_name="i5", ram_gb=8.0, disk_free_gb=50.0)
    verdict = HardwareVerdict(overall="green", cpu_status="green", ram_status="green", disk_status="green")
    defaults = dict(hardware=hw, hardware_verdict=verdict, apps=[])
    defaults.update(kwargs)
    return Report(**defaults)


def test_report_generated_at_set_automatically() -> None:
    r = _make_report()
    assert r.generated_at is not None


def test_report_counts_empty() -> None:
    r = _make_report()
    assert r.green_count == 0
    assert r.yellow_count == 0
    assert r.red_count == 0


def test_report_counts() -> None:
    apps = [
        AppMatch(windows_app=WindowsApp(name="VLC"), category="green", linux_package="vlc", install_via="apt"),
        AppMatch(windows_app=WindowsApp(name="MS Office"), category="yellow", linux_package="libreoffice", install_via="apt"),
        AppMatch(windows_app=WindowsApp(name="Adobe Premiere"), category="red"),
        AppMatch(windows_app=WindowsApp(name="Firefox"), category="green", linux_package="firefox", install_via="apt"),
    ]
    r = _make_report(apps=apps)
    assert r.green_count == 2
    assert r.yellow_count == 1
    assert r.red_count == 1


def test_install_command_apt_only() -> None:
    apps = [
        AppMatch(windows_app=WindowsApp(name="VLC"), category="green", linux_package="vlc", install_via="apt"),
        AppMatch(windows_app=WindowsApp(name="Firefox"), category="green", linux_package="firefox", install_via="apt"),
    ]
    r = _make_report(apps=apps)
    assert r.install_command.startswith("sudo apt install -y")
    assert "firefox" in r.install_command
    assert "vlc" in r.install_command


def test_install_command_flatpak_only() -> None:
    apps = [
        AppMatch(windows_app=WindowsApp(name="GIMP"), category="green", linux_package="org.gimp.GIMP", install_via="flatpak"),
    ]
    r = _make_report(apps=apps)
    assert "flatpak install -y flathub org.gimp.GIMP" in r.install_command
    assert "sudo apt" not in r.install_command


def test_install_command_mixed() -> None:
    apps = [
        AppMatch(windows_app=WindowsApp(name="VLC"), category="green", linux_package="vlc", install_via="apt"),
        AppMatch(windows_app=WindowsApp(name="GIMP"), category="green", linux_package="org.gimp.GIMP", install_via="flatpak"),
    ]
    r = _make_report(apps=apps)
    assert "sudo apt install -y" in r.install_command
    assert "flatpak install -y flathub org.gimp.GIMP" in r.install_command


def test_install_command_deduplicates() -> None:
    # Two apps mapping to the same package should not repeat it
    apps = [
        AppMatch(windows_app=WindowsApp(name="App A"), category="green", linux_package="vlc", install_via="apt"),
        AppMatch(windows_app=WindowsApp(name="App B"), category="green", linux_package="vlc", install_via="apt"),
    ]
    r = _make_report(apps=apps)
    assert r.install_command.count("vlc") == 1


def test_install_command_empty_when_no_packages() -> None:
    apps = [AppMatch(windows_app=WindowsApp(name="Adobe Premiere"), category="red")]
    r = _make_report(apps=apps)
    assert r.install_command == ""


def test_report_serialization() -> None:
    r = _make_report()
    data = r.model_dump()
    assert "hardware" in data
    assert "green_count" in data       # computed fields included
    assert "install_command" in data
