"""Unit tests for windowstolinux.output (html_renderer and pdf_exporter)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from windowstolinux.models import (
    AppMatch,
    HardwareInfo,
    HardwareVerdict,
    Report,
    WindowsApp,
)
from windowstolinux.output.html_renderer import render_html
from windowstolinux.output.pdf_exporter import export_pdf


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _hw(**kwargs) -> HardwareInfo:
    defaults = dict(
        cpu_64bit=True,
        cpu_cores=4,
        cpu_name="Intel Core i5-12400",
        ram_gb=8.0,
        disk_free_gb=60.0,
    )
    defaults.update(kwargs)
    return HardwareInfo(**defaults)


def _verdict(**kwargs) -> HardwareVerdict:
    defaults = dict(overall="green", cpu_status="green", ram_status="green", disk_status="green")
    defaults.update(kwargs)
    return HardwareVerdict(**defaults)


def _match(name: str, category: str, pkg: str | None = None, via=None, note: str | None = None) -> AppMatch:
    return AppMatch(
        windows_app=WindowsApp(name=name),
        category=category,
        linux_package=pkg,
        install_via=via,
        note=note,
    )


def _report(**kwargs) -> Report:
    defaults = dict(
        hardware=_hw(),
        hardware_verdict=_verdict(),
        apps=[],
        generated_at=datetime(2026, 4, 1, 14, 30),
    )
    defaults.update(kwargs)
    return Report(**defaults)


# ---------------------------------------------------------------------------
# render_html - structure
# ---------------------------------------------------------------------------


def test_render_html_returns_string() -> None:
    html = render_html(_report())
    assert isinstance(html, str)
    assert len(html) > 100


def test_render_html_is_valid_html() -> None:
    html = render_html(_report())
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "</html>" in html


def test_render_html_has_german_title() -> None:
    html = render_html(_report())
    assert "Linux-Migrationsbericht" in html


def test_render_html_contains_generated_date() -> None:
    html = render_html(_report())
    assert "01.04.2026" in html
    assert "14:30" in html


# ---------------------------------------------------------------------------
# render_html - hardware section
# ---------------------------------------------------------------------------


def test_render_html_contains_cpu_name() -> None:
    html = render_html(_report(hardware=_hw(cpu_name="AMD Ryzen 7 5800X")))
    assert "AMD Ryzen 7 5800X" in html


def test_render_html_contains_ram() -> None:
    html = render_html(_report(hardware=_hw(ram_gb=16.0)))
    assert "16" in html


def test_render_html_contains_disk() -> None:
    html = render_html(_report(hardware=_hw(disk_free_gb=120.0)))
    assert "120" in html


def test_render_html_shows_gpu_when_present() -> None:
    html = render_html(_report(hardware=_hw(gpu_name="NVIDIA RTX 3060")))
    assert "NVIDIA RTX 3060" in html


def test_render_html_omits_gpu_section_when_absent() -> None:
    html = render_html(_report(hardware=_hw(gpu_name=None)))
    assert "Grafikkarte" not in html


def test_render_html_shows_wlan_when_present() -> None:
    html = render_html(_report(hardware=_hw(wlan_chipset="Intel AX210")))
    assert "Intel AX210" in html


def test_render_html_omits_wlan_section_when_absent() -> None:
    html = render_html(_report(hardware=_hw(wlan_chipset=None)))
    assert "WLAN-Chip" not in html


def test_render_html_shows_manufacturer_in_header() -> None:
    html = render_html(_report(hardware=_hw(manufacturer="Lenovo", model="ThinkPad X1")))
    assert "Lenovo" in html
    assert "ThinkPad X1" in html


def test_render_html_hardware_verdict_green_text() -> None:
    html = render_html(_report(hardware_verdict=_verdict(overall="green")))
    assert "gut für Linux Mint geeignet" in html


def test_render_html_hardware_verdict_yellow_text() -> None:
    html = render_html(_report(hardware_verdict=_verdict(overall="yellow", ram_status="yellow")))
    assert "bedingt" in html


def test_render_html_hardware_verdict_red_text() -> None:
    html = render_html(_report(hardware_verdict=_verdict(overall="red", cpu_status="red")))
    assert "Mindestanforderungen" in html


def test_render_html_shows_issues() -> None:
    v = _verdict(overall="yellow", ram_status="yellow", issues=["Nur 3.0 GB RAM vorhanden."])
    html = render_html(_report(hardware_verdict=v))
    assert "Nur 3.0 GB RAM vorhanden." in html


def test_render_html_shows_boot_key_hint() -> None:
    v = _verdict(boot_key_hint="F12")
    html = render_html(_report(hardware_verdict=v))
    assert "F12" in html


def test_render_html_no_boot_hint_section_when_absent() -> None:
    html = render_html(_report(hardware_verdict=_verdict(boot_key_hint=None)))
    assert "Boot-Menue" not in html


# ---------------------------------------------------------------------------
# render_html - apps section
# ---------------------------------------------------------------------------


def test_render_html_shows_green_app() -> None:
    apps = [_match("VLC media player", "green", "vlc", "apt")]
    html = render_html(_report(apps=apps))
    assert "VLC media player" in html
    assert "vlc" in html


def test_render_html_shows_yellow_app_with_note() -> None:
    apps = [_match("Microsoft Office", "yellow", "libreoffice", "apt", "LibreOffice als Alternative")]
    html = render_html(_report(apps=apps))
    assert "Microsoft Office" in html
    assert "LibreOffice als Alternative" in html


def test_render_html_shows_red_app() -> None:
    apps = [_match("SomeWinTool", "red", note="Kein Linux-Aequivalent.")]
    html = render_html(_report(apps=apps))
    assert "SomeWinTool" in html


def test_render_html_shows_apt_via_label() -> None:
    apps = [_match("Firefox", "green", "firefox", "apt")]
    html = render_html(_report(apps=apps))
    assert "apt" in html


def test_render_html_shows_flatpak_via_label() -> None:
    apps = [_match("GIMP", "green", "org.gimp.GIMP", "flatpak")]
    html = render_html(_report(apps=apps))
    assert "Flatpak" in html


def test_render_html_counts_in_group_headers() -> None:
    apps = [
        _match("App1", "green", "pkg1", "apt"),
        _match("App2", "green", "pkg2", "apt"),
        _match("App3", "yellow", "pkg3", "apt", "note"),
        _match("App4", "red"),
    ]
    html = render_html(_report(apps=apps))
    assert "Direkt verfügbar (2)" in html
    assert "Alternative vorhanden (1)" in html
    assert "Kein Linux-Äquivalent (1)" in html


def test_render_html_empty_apps_list() -> None:
    html = render_html(_report(apps=[]))
    assert "Programme gesamt" in html
    assert "0" in html


def test_render_html_stats_bar_shows_counts() -> None:
    apps = [
        _match("A", "green", "a", "apt"),
        _match("B", "yellow", "b", "apt", "note"),
        _match("C", "red"),
    ]
    html = render_html(_report(apps=apps))
    # All three counts should appear
    assert "Direkt verfügbar" in html
    assert "Alternative vorhanden" in html
    assert "Kein Äquivalent" in html


# ---------------------------------------------------------------------------
# render_html - install command
# ---------------------------------------------------------------------------


def test_render_html_shows_install_command() -> None:
    apps = [_match("Firefox", "green", "firefox", "apt")]
    html = render_html(_report(apps=apps))
    assert "sudo apt install -y" in html
    assert "firefox" in html


def test_render_html_no_install_section_when_all_red() -> None:
    apps = [_match("WinOnlyApp", "red")]
    html = render_html(_report(apps=apps))
    # The <h2> heading only renders when there is an install command.
    # The word "Installations-Befehl" can still appear in "Naechste Schritte".
    assert "<h2>Installations-Befehl</h2>" not in html


# ---------------------------------------------------------------------------
# render_html - next steps section
# ---------------------------------------------------------------------------


def test_render_html_has_next_steps() -> None:
    html = render_html(_report())
    assert "linuxmint.com" in html
    assert "Balena Etcher" in html
    assert "Installations-Assistent" in html
    assert "Terminal" in html


def test_render_html_next_steps_includes_boot_key() -> None:
    v = _verdict(boot_key_hint="F9")
    html = render_html(_report(hardware_verdict=v))
    # F9 appears in both the boot hint and the next steps
    assert html.count("F9") >= 2


# ---------------------------------------------------------------------------
# pdf_exporter
# ---------------------------------------------------------------------------


def test_export_pdf_calls_weasyprint(tmp_path) -> None:
    output = tmp_path / "report.pdf"
    mock_instance = MagicMock()
    mock_wp = MagicMock(HTML=MagicMock(return_value=mock_instance))

    with patch("builtins.__import__", side_effect=lambda name, *a, **kw:
               mock_wp if name == "weasyprint" else __import__(name, *a, **kw)):
        export_pdf("<html></html>", output)

    mock_wp.HTML.assert_called_once_with(string="<html></html>")
    mock_instance.write_pdf.assert_called_once_with(str(output))


def test_export_pdf_creates_parent_dirs(tmp_path, mocker) -> None:
    nested = tmp_path / "a" / "b" / "report.pdf"
    mock_wp_instance = MagicMock()
    mock_wp_module = MagicMock()
    mock_wp_module.HTML.return_value = mock_wp_instance

    with patch("builtins.__import__", side_effect=lambda name, *a, **kw:
               mock_wp_module if name == "weasyprint" else __import__(name, *a, **kw)):
        export_pdf("<html></html>", nested)

    assert nested.parent.exists()


def test_export_pdf_reraises_weasyprint_error(tmp_path, mocker) -> None:
    mock_wp_module = MagicMock()
    mock_wp_module.HTML.return_value.write_pdf.side_effect = RuntimeError("GTK not found")

    with pytest.raises(RuntimeError, match="GTK not found"):
        with patch("builtins.__import__", side_effect=lambda name, *a, **kw:
                   mock_wp_module if name == "weasyprint" else __import__(name, *a, **kw)):
            export_pdf("<html></html>", tmp_path / "report.pdf")
