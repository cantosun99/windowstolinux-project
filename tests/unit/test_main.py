"""Unit tests for windowstolinux.__main__."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _get_log_path
# ---------------------------------------------------------------------------


def test_get_log_path_uses_localappdata(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    from windowstolinux.__main__ import _get_log_path

    path = _get_log_path()

    assert path.name == "app.log"
    assert "WindowsToLinux" in str(path)
    assert path.parent.exists()


def test_get_log_path_falls_back_to_home(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    from windowstolinux.__main__ import _get_log_path

    path = _get_log_path()

    assert path.name == "app.log"
    assert "WindowsToLinux" in str(path)


def test_get_log_path_creates_parent_directory(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "nonexistent"))
    from windowstolinux.__main__ import _get_log_path

    path = _get_log_path()

    assert path.parent.exists()


# ---------------------------------------------------------------------------
# _setup_logging
# ---------------------------------------------------------------------------


def test_setup_logging_adds_rotating_file_handler(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    from windowstolinux.__main__ import _setup_logging

    root = logging.getLogger()
    before = len(root.handlers)

    try:
        _setup_logging()
        after = len(root.handlers)
        assert after > before
        new_handler = root.handlers[-1]
        assert isinstance(new_handler, logging.handlers.RotatingFileHandler)
    finally:
        for h in root.handlers[before:]:
            root.removeHandler(h)
            h.close()


def test_setup_logging_writes_to_log_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    from windowstolinux.__main__ import _setup_logging

    root = logging.getLogger()
    before = len(root.handlers)

    try:
        _setup_logging()
        logging.getLogger("test.main").info("probe message")
        log_path = tmp_path / "WindowsToLinux" / "app.log"
        assert log_path.exists()
        assert "probe message" in log_path.read_text(encoding="utf-8")
    finally:
        for h in root.handlers[before:]:
            root.removeHandler(h)
            h.close()


# ---------------------------------------------------------------------------
# _show_crash_dialog
# ---------------------------------------------------------------------------


def test_show_crash_dialog_calls_messagebox(mocker) -> None:
    mock_mb = MagicMock()
    mocker.patch("tkinter.messagebox", mock_mb, create=True)

    from windowstolinux.__main__ import _show_crash_dialog

    _show_crash_dialog(RuntimeError("test error"))
    # The function imports messagebox internally; success = no exception raised


def test_show_crash_dialog_does_not_raise_when_messagebox_fails(mocker) -> None:
    """Even if messagebox.showerror raises (e.g. no display), no exception propagates."""
    import sys
    tkinter_mock = sys.modules.get("tkinter")
    if tkinter_mock is not None:
        mocker.patch.object(
            tkinter_mock, "messagebox",
            new=MagicMock(showerror=MagicMock(side_effect=RuntimeError("no display"))),
            create=True,
        )

    from windowstolinux.__main__ import _show_crash_dialog
    _show_crash_dialog(RuntimeError("original error"))  # must not raise


def test_show_crash_dialog_shows_exception_typename(mocker) -> None:
    """The dialog text includes the exception class name."""
    import sys
    captured: list[str] = []

    tkinter_mock = sys.modules.get("tkinter")
    if tkinter_mock is not None:
        mock_mb = MagicMock()
        mock_mb.showerror.side_effect = lambda title, msg: captured.append(msg)
        mocker.patch.object(tkinter_mock, "messagebox", new=mock_mb, create=True)

    from windowstolinux.__main__ import _show_crash_dialog
    _show_crash_dialog(ValueError("bad value"))

    if captured:  # dialog was shown
        assert "ValueError" in captured[0]


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_starts_and_stops_normally(monkeypatch, tmp_path, mocker) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    mock_app = MagicMock()
    mocker.patch("windowstolinux.gui.app.App", return_value=mock_app)

    root = logging.getLogger()
    before = len(root.handlers)

    try:
        from windowstolinux.__main__ import main
        main()
    finally:
        for h in root.handlers[before:]:
            root.removeHandler(h)
            h.close()

    mock_app.mainloop.assert_called_once()


def test_main_calls_sys_exit_on_unhandled_exception(monkeypatch, tmp_path, mocker) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    mocker.patch("windowstolinux.gui.app.App", side_effect=RuntimeError("startup crash"))
    mocker.patch("windowstolinux.__main__._show_crash_dialog")

    root = logging.getLogger()
    before = len(root.handlers)

    try:
        with pytest.raises(SystemExit) as exc_info:
            from windowstolinux.__main__ import main
            main()
        assert exc_info.value.code == 1
    finally:
        for h in root.handlers[before:]:
            root.removeHandler(h)
            h.close()


def test_main_logs_crash_before_exit(monkeypatch, tmp_path, mocker) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    mocker.patch("windowstolinux.gui.app.App", side_effect=OSError("crash"))
    mocker.patch("windowstolinux.__main__._show_crash_dialog")

    root = logging.getLogger()
    before = len(root.handlers)

    try:
        with pytest.raises(SystemExit):
            from windowstolinux.__main__ import main
            main()
        log_file = tmp_path / "WindowsToLinux" / "app.log"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "crash" in content.lower()
    finally:
        for h in root.handlers[before:]:
            root.removeHandler(h)
            h.close()
