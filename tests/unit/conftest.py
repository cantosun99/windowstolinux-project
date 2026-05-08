"""
Pytest configuration for unit tests.

Mocks tkinter and customtkinter on systems where Tk is not installed
(headless CI, Python builds without Tk). This allows importing gui/app.py
and the screen modules so that the display-independent functions
run_scan() and export_report() can be unit-tested.
"""

import sys
from unittest.mock import MagicMock


class _MockWidget:
    """Minimal stand-in for CTk base classes (import-time only)."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def pack(self, **kwargs) -> None:
        pass

    def configure(self, **kwargs) -> None:
        pass

    def winfo_exists(self) -> bool:
        return True

    def after(self, ms: int, func=None, *args) -> None:
        if func is not None:
            func(*args)

    def destroy(self) -> None:
        pass

    def start(self) -> None:
        pass


def _mock_ctk() -> MagicMock:
    m = MagicMock()
    m.CTk = _MockWidget
    m.CTkFrame = _MockWidget
    m.CTkLabel = _MockWidget
    m.CTkButton = _MockWidget
    m.CTkProgressBar = _MockWidget
    m.CTkFont = MagicMock
    return m


# ------------------------------------------------------------------
# Conditionally mock unavailable libraries before any test module
# imports them. Uses setdefault so real modules are never replaced.
# ------------------------------------------------------------------

import pytest


@pytest.fixture(autouse=True)
def _no_repology_rate_limit(monkeypatch):
    """Disable the Repology rate limiter for all unit tests."""
    import windowstolinux.resolver.repology as rep
    monkeypatch.setattr(rep, "_MIN_REQUEST_INTERVAL", 0.0)


try:
    import _tkinter  # noqa: F401
except ImportError:
    _tk = MagicMock()
    for _mod in ("_tkinter", "tkinter", "tkinter.ttk", "tkinter.messagebox", "tkinter.filedialog"):
        sys.modules.setdefault(_mod, _tk)
    sys.modules.setdefault("customtkinter", _mock_ctk())
