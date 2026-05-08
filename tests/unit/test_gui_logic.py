"""Unit tests for the GUI business logic functions in gui/app.py.

CTk widgets cannot be instantiated without a display, so these tests
cover only the display-independent functions run_scan() and
export_report() that contain all meaningful logic.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from windowstolinux.gui.app import export_report, run_scan
from windowstolinux.models import (
    AppMatch,
    HardwareInfo,
    HardwareVerdict,
    Report,
    WindowsApp,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hw() -> HardwareInfo:
    return HardwareInfo(
        cpu_64bit=True, cpu_cores=4, cpu_name="i5",
        ram_gb=8.0, disk_free_gb=60.0,
    )


def _verdict() -> HardwareVerdict:
    return HardwareVerdict(
        overall="green", cpu_status="green",
        ram_status="green", disk_status="green",
    )


def _report() -> Report:
    return Report(hardware=_hw(), hardware_verdict=_verdict(), apps=[])


# ---------------------------------------------------------------------------
# run_scan
# ---------------------------------------------------------------------------


def test_run_scan_returns_report(mocker) -> None:
    mocker.patch("windowstolinux.gui.app.scan_hardware", return_value=_hw())
    mocker.patch("windowstolinux.gui.app.check_hardware", return_value=_verdict())
    mocker.patch("windowstolinux.gui.app.scan_installed_apps", return_value=[])
    mocker.patch("windowstolinux.gui.app.classify_all", return_value=[])

    report = run_scan(on_status=lambda _: None)

    assert isinstance(report, Report)


def test_run_scan_calls_pipeline_in_order(mocker) -> None:
    calls: list[str] = []

    def mock_scan_hw():
        calls.append("scan_hardware")
        return _hw()

    def mock_check_hw(hw):
        calls.append("check_hardware")
        return _verdict()

    def mock_scan_apps():
        calls.append("scan_installed_apps")
        return []

    def mock_classify(apps):
        calls.append("classify_all")
        return []

    mocker.patch("windowstolinux.gui.app.scan_hardware", side_effect=mock_scan_hw)
    mocker.patch("windowstolinux.gui.app.check_hardware", side_effect=mock_check_hw)
    mocker.patch("windowstolinux.gui.app.scan_installed_apps", side_effect=mock_scan_apps)
    mocker.patch("windowstolinux.gui.app.classify_all", side_effect=mock_classify)

    run_scan(on_status=lambda _: None)

    assert calls == ["scan_hardware", "check_hardware", "scan_installed_apps", "classify_all"]


def test_run_scan_emits_four_status_updates(mocker) -> None:
    mocker.patch("windowstolinux.gui.app.scan_hardware", return_value=_hw())
    mocker.patch("windowstolinux.gui.app.check_hardware", return_value=_verdict())
    mocker.patch("windowstolinux.gui.app.scan_installed_apps", return_value=[])
    mocker.patch("windowstolinux.gui.app.classify_all", return_value=[])

    statuses: list[str] = []
    run_scan(on_status=statuses.append)

    assert len(statuses) == 4


def test_run_scan_status_messages_are_german(mocker) -> None:
    mocker.patch("windowstolinux.gui.app.scan_hardware", return_value=_hw())
    mocker.patch("windowstolinux.gui.app.check_hardware", return_value=_verdict())
    mocker.patch("windowstolinux.gui.app.scan_installed_apps", return_value=[])
    mocker.patch("windowstolinux.gui.app.classify_all", return_value=[])

    statuses: list[str] = []
    run_scan(on_status=statuses.append)

    assert all(isinstance(s, str) and len(s) > 5 for s in statuses)
    assert any("Hardware" in s for s in statuses)
    assert any("Programme" in s for s in statuses)


def test_run_scan_status_includes_app_count(mocker) -> None:
    apps = [WindowsApp(name="VLC"), WindowsApp(name="Firefox")]
    mocker.patch("windowstolinux.gui.app.scan_hardware", return_value=_hw())
    mocker.patch("windowstolinux.gui.app.check_hardware", return_value=_verdict())
    mocker.patch("windowstolinux.gui.app.scan_installed_apps", return_value=apps)
    mocker.patch("windowstolinux.gui.app.classify_all", return_value=[])

    statuses: list[str] = []
    run_scan(on_status=statuses.append)

    assert any("2" in s for s in statuses)


def test_run_scan_passes_apps_to_classify_all(mocker) -> None:
    apps = [WindowsApp(name="VLC"), WindowsApp(name="GIMP")]
    mocker.patch("windowstolinux.gui.app.scan_hardware", return_value=_hw())
    mocker.patch("windowstolinux.gui.app.check_hardware", return_value=_verdict())
    mocker.patch("windowstolinux.gui.app.scan_installed_apps", return_value=apps)
    mock_classify = mocker.patch("windowstolinux.gui.app.classify_all", return_value=[])

    run_scan(on_status=lambda _: None)

    mock_classify.assert_called_once_with(apps)


def test_run_scan_propagates_exception(mocker) -> None:
    mocker.patch("windowstolinux.gui.app.scan_hardware", side_effect=RuntimeError("WMI crash"))

    with pytest.raises(RuntimeError, match="WMI crash"):
        run_scan(on_status=lambda _: None)


# ---------------------------------------------------------------------------
# export_report
# ---------------------------------------------------------------------------


def test_export_report_calls_render_then_pdf(mocker, tmp_path) -> None:
    mock_render = mocker.patch("windowstolinux.gui.app.render_html", return_value="<html>ok</html>")
    mock_pdf = mocker.patch("windowstolinux.gui.app.export_pdf")

    report = _report()
    output = tmp_path / "report.pdf"
    export_report(report, output)

    mock_render.assert_called_once_with(report)
    mock_pdf.assert_called_once_with("<html>ok</html>", output)


def test_export_report_passes_correct_path(mocker, tmp_path) -> None:
    mocker.patch("windowstolinux.gui.app.render_html", return_value="<html>")
    mock_pdf = mocker.patch("windowstolinux.gui.app.export_pdf")

    target = tmp_path / "subdir" / "out.pdf"
    export_report(_report(), target)

    mock_pdf.assert_called_once_with("<html>", target)


def test_export_report_propagates_pdf_error(mocker, tmp_path) -> None:
    mocker.patch("windowstolinux.gui.app.render_html", return_value="<html>")
    mocker.patch("windowstolinux.gui.app.export_pdf", side_effect=OSError("disk full"))

    with pytest.raises(OSError, match="disk full"):
        export_report(_report(), tmp_path / "report.pdf")
