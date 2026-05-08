"""Integration tests for the full scan-to-report pipeline.

These tests exercise the complete chain from hardware scan through app
classification to HTML rendering. Only OS-specific calls (psutil, winreg,
WMI) and external HTTP requests are mocked; all business logic, static
data, and the Jinja2 template run for real.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from windowstolinux.matcher.app_classifier import classify_all
from windowstolinux.matcher.hardware_check import check_hardware
from windowstolinux.models import AppMatch, Report
from windowstolinux.output.html_renderer import render_html
from windowstolinux.scanner.apps import scan_installed_apps
from windowstolinux.scanner.hardware import scan_hardware


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("WINDOWSTOLINUX_CACHE_PATH", str(tmp_path / "cache.db"))


@pytest.fixture()
def mock_hardware(mocker):
    """Return a realistic Lenovo ThinkPad with good specs."""
    mocker.patch("windowstolinux.scanner.hardware.platform.machine", return_value="AMD64")
    mocker.patch("windowstolinux.scanner.hardware.psutil.cpu_count", return_value=4)

    vm = MagicMock()
    vm.total = 8 * 1024 ** 3
    mocker.patch("windowstolinux.scanner.hardware.psutil.virtual_memory", return_value=vm)

    du = MagicMock()
    du.free = 60 * 1024 ** 3
    mocker.patch("windowstolinux.scanner.hardware.psutil.disk_usage", return_value=du)

    mocker.patch(
        "windowstolinux.scanner.hardware._query_wmi",
        return_value=("Intel Core i5-12400", "Intel Iris Xe", "Intel AX210", "Lenovo", "ThinkPad X1"),
    )


@pytest.fixture()
def mock_hardware_borderline(mocker):
    """32-bit CPU + low RAM + tiny disk - worst case."""
    mocker.patch("windowstolinux.scanner.hardware.platform.machine", return_value="x86")
    mocker.patch("windowstolinux.scanner.hardware.psutil.cpu_count", return_value=2)

    vm = MagicMock()
    vm.total = int(1.5 * 1024 ** 3)
    mocker.patch("windowstolinux.scanner.hardware.psutil.virtual_memory", return_value=vm)

    du = MagicMock()
    du.free = 10 * 1024 ** 3
    mocker.patch("windowstolinux.scanner.hardware.psutil.disk_usage", return_value=du)

    mocker.patch(
        "windowstolinux.scanner.hardware._query_wmi",
        return_value=("Intel Atom", None, None, "HP", "Pavilion"),
    )


def _registry_entries(names: list[str]):
    """Build minimal registry entry dicts from a list of display names."""
    return iter({"DisplayName": n} for n in names)


def _make_http_dispatcher(**url_responses: object):
    """Return an httpx.get side_effect that dispatches by URL substring.

    url_responses: keyword mapping of URL substring -> json return value.
    A key of "default" is used when nothing else matches.
    """
    def _get(url: str, **kwargs):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        for fragment, data in url_responses.items():
            if fragment == "default" or fragment in url:
                resp.json.return_value = data
                return resp
        resp.json.return_value = []
        return resp
    return _get


def _mock_http_no_results(mocker) -> None:
    """Make Repology and Flathub return empty responses (no matches).

    Both modules share the same httpx module object, so a single patch
    on httpx.get with URL-based dispatch is used.
    """
    mocker.patch(
        "httpx.get",
        side_effect=_make_http_dispatcher(
            flathub={"apps": []},
            default=[],           # repology: empty list = not found
        ),
    )


# ---------------------------------------------------------------------------
# Hardware scan + verdict
# ---------------------------------------------------------------------------


def test_hardware_scan_and_verdict_green(mock_hardware) -> None:
    hw = scan_hardware()
    verdict = check_hardware(hw)

    assert hw.cpu_64bit is True
    assert hw.cpu_cores == 4
    assert hw.ram_gb == pytest.approx(8.0, abs=0.1)
    assert hw.manufacturer == "Lenovo"
    assert verdict.overall == "green"
    assert verdict.boot_key_hint == "F12"
    assert verdict.issues == []


def test_hardware_scan_and_verdict_all_red(mock_hardware_borderline) -> None:
    hw = scan_hardware()
    verdict = check_hardware(hw)

    assert hw.cpu_64bit is False
    assert verdict.overall == "red"
    assert verdict.cpu_status == "red"
    assert verdict.ram_status == "red"
    assert verdict.disk_status == "red"
    assert len(verdict.issues) == 3
    assert verdict.boot_key_hint == "F9"


# ---------------------------------------------------------------------------
# App scan + classification
# ---------------------------------------------------------------------------


def test_app_classification_static_mapping_hit(mocker) -> None:
    """Apps in windows_to_linux_mapping.json with version noise get matched."""
    _mock_http_no_results(mocker)
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=_registry_entries([
            "VLC media player 3.0.20",
            "Mozilla Firefox 123.0.1 (x64 de)",
            "7-Zip 23.01 (x64)",
        ]),
    )

    apps = scan_installed_apps()
    matches = classify_all(apps)

    by_name = {m.windows_app.name: m for m in matches}
    assert by_name["VLC media player 3.0.20"].category == "green"
    assert by_name["VLC media player 3.0.20"].linux_package == "vlc"
    assert by_name["Mozilla Firefox 123.0.1 (x64 de)"].category == "green"
    assert by_name["7-Zip 23.01 (x64)"].category == "green"


def test_app_classification_prefix_match(mocker) -> None:
    """Long Office variant name matches the 'microsoft office' mapping key."""
    _mock_http_no_results(mocker)
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=_registry_entries([
            "Microsoft Office Professional Plus 2019 - de-de",
        ]),
    )

    apps = scan_installed_apps()
    matches = classify_all(apps)

    assert len(matches) == 1
    assert matches[0].category == "yellow"
    assert matches[0].linux_package == "libreoffice"


def test_app_classification_alternatives_fallback(mocker) -> None:
    """App in opensource_alternatives.json (not in main mapping) -> yellow."""
    _mock_http_no_results(mocker)
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=_registry_entries(["HandBrake 1.6.1"]),
    )

    apps = scan_installed_apps()
    matches = classify_all(apps)

    assert matches[0].category == "yellow"
    assert "HandBrake" in (matches[0].note or "")


def test_app_classification_red_when_no_match(mocker) -> None:
    """Unknown proprietary tool -> red."""
    _mock_http_no_results(mocker)
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=_registry_entries(["SuperSpecialWindowsTool 9000"]),
    )

    apps = scan_installed_apps()
    matches = classify_all(apps)

    assert matches[0].category == "red"
    assert "Wine" in (matches[0].note or "")


def test_app_classification_repology_hit(mocker) -> None:
    """Package found on Repology -> green via apt.

    Uses "VeraCrypt" which is not in any static mapping, so Repology
    is actually queried and the result drives the classification.
    Both resolver modules share one httpx.get; a URL dispatcher separates them.
    """
    mocker.patch(
        "httpx.get",
        side_effect=_make_http_dispatcher(
            repology=[{"repo": "ubuntu_24_04", "binname": "veracrypt", "srcname": "veracrypt"}],
            flathub={"apps": []},
        ),
    )
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=_registry_entries(["VeraCrypt 1.26.14"]),
    )

    apps = scan_installed_apps()
    matches = classify_all(apps)

    assert matches[0].category == "green"
    assert matches[0].linux_package == "veracrypt"
    assert matches[0].install_via == "apt"


def test_app_classification_flathub_hit(mocker) -> None:
    """Package found on Flathub with plausible ID -> green via flatpak."""
    mocker.patch(
        "httpx.get",
        side_effect=_make_http_dispatcher(
            flathub={"apps": [{"id": "com.obsproject.Studio"}]},
            default=[],
        ),
    )
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=_registry_entries(["OBS Studio 30.2"]),
    )

    apps = scan_installed_apps()
    matches = classify_all(apps)

    assert matches[0].category == "green"
    assert matches[0].linux_package == "com.obsproject.Studio"
    assert matches[0].install_via == "flatpak"


def test_app_dedup_strips_version_differences(mocker) -> None:
    """Two entries differing only by version -> deduplicated to one."""
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=_registry_entries([
            "VLC media player 3.0.20",
            "VLC media player 3.0.18",
        ]),
    )
    apps = scan_installed_apps()
    assert len(apps) == 1


def test_system_components_filtered_before_classification(mocker) -> None:
    """Blacklisted system entries never reach the classifier."""
    _mock_http_no_results(mocker)
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=_registry_entries([
            "Microsoft Visual C++ 2019 Redistributable (x64)",
            "VLC media player",
        ]),
    )

    apps = scan_installed_apps()
    assert len(apps) == 1
    assert apps[0].name == "VLC media player"


# ---------------------------------------------------------------------------
# Full pipeline: hardware + apps -> Report -> HTML
# ---------------------------------------------------------------------------


def test_full_pipeline_produces_valid_report(mock_hardware, mocker) -> None:
    _mock_http_no_results(mocker)
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=_registry_entries([
            "VLC media player 3.0.20",
            "Mozilla Firefox 123.0.1 (x64 de)",
            "Microsoft Office Professional Plus 2019",
            "HandBrake 1.6.1",
            "SomeWindowsOnlyApp 5.0",
        ]),
    )

    hw = scan_hardware()
    verdict = check_hardware(hw)
    apps = scan_installed_apps()
    matches = classify_all(apps)
    report = Report(hardware=hw, hardware_verdict=verdict, apps=matches)

    assert report.green_count >= 2
    assert report.yellow_count >= 1
    assert report.red_count >= 1
    assert report.green_count + report.yellow_count + report.red_count == len(matches)


def test_full_pipeline_html_contains_app_names(mock_hardware, mocker) -> None:
    _mock_http_no_results(mocker)
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=_registry_entries([
            "VLC media player 3.0.20",
            "Microsoft Office Professional Plus 2019",
        ]),
    )

    hw = scan_hardware()
    verdict = check_hardware(hw)
    apps = scan_installed_apps()
    matches = classify_all(apps)
    report = Report(hardware=hw, hardware_verdict=verdict, apps=matches)
    html = render_html(report)

    # Original registry names must appear in the report (not the normalized ones)
    assert "VLC media player 3.0.20" in html
    assert "Microsoft Office Professional Plus 2019" in html
    assert "libreoffice" in html        # the linux package
    assert "vlc" in html
    assert "Lenovo" in html             # from hardware
    assert "F12" in html                # boot key hint


def test_full_pipeline_install_command_is_valid(mock_hardware, mocker) -> None:
    _mock_http_no_results(mocker)
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=_registry_entries([
            "VLC media player",
            "Mozilla Firefox",
            "GIMP 2.10",
        ]),
    )

    hw = scan_hardware()
    verdict = check_hardware(hw)
    apps = scan_installed_apps()
    matches = classify_all(apps)
    report = Report(hardware=hw, hardware_verdict=verdict, apps=matches)

    cmd = report.install_command
    assert "sudo apt install -y" in cmd
    assert "vlc" in cmd
    assert "firefox" in cmd
    assert "flatpak install" in cmd     # GIMP is flatpak


def test_html_report_empty_app_list(mock_hardware) -> None:
    """Report with zero apps renders without error."""
    hw = scan_hardware()
    verdict = check_hardware(hw)
    report = Report(hardware=hw, hardware_verdict=verdict, apps=[])
    html = render_html(report)

    assert "0" in html
    assert "Programme gesamt" in html
    assert "Keine Programme direkt verfügbar" in html


def test_network_error_falls_back_to_stale_cache(mock_hardware, mocker, monkeypatch) -> None:
    """Cache miss + network down -> stale cache entry used, report still built."""
    import windowstolinux.resolver.cache as cache_mod
    from windowstolinux.resolver import cache

    # Pre-populate a stale Repology hit for "veracrypt" (not in any static data)
    cache.set("repology:veracrypt", "veracrypt")
    monkeypatch.setattr(cache_mod, "_TTL_SECONDS", 0)  # expire everything

    import httpx as _httpx
    mocker.patch("httpx.get", side_effect=_httpx.ConnectError("offline"))
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=_registry_entries(["VeraCrypt 1.26.14"]),
    )

    apps = scan_installed_apps()
    matches = classify_all(apps)
    hw = scan_hardware()
    verdict = check_hardware(hw)
    report = Report(hardware=hw, hardware_verdict=verdict, apps=matches)

    # Stale cache hit -> still classified as green via apt
    assert matches[0].category == "green"
    assert matches[0].linux_package == "veracrypt"
    html = render_html(report)
    assert "VeraCrypt 1.26.14" in html
