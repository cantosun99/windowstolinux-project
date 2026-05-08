"""Unit tests for windowstolinux.resolver.mappings."""

from __future__ import annotations

import json

import pytest

import windowstolinux.resolver.mappings as mappings_mod
from windowstolinux.resolver.mappings import load_opensource_alternatives, load_windows_to_linux


# ---------------------------------------------------------------------------
# load_windows_to_linux
# ---------------------------------------------------------------------------


def test_load_windows_to_linux_returns_dict() -> None:
    result = load_windows_to_linux()
    assert isinstance(result, dict)


def test_load_windows_to_linux_has_expected_keys() -> None:
    result = load_windows_to_linux()
    # Keys defined in data/windows_to_linux_mapping.json
    assert "7-zip" in result
    assert "vlc media player" in result


def test_load_windows_to_linux_entry_has_required_fields() -> None:
    result = load_windows_to_linux()
    entry = result["7-zip"]
    assert "linux_package" in entry
    assert "install_via" in entry
    assert "category" in entry


def test_load_windows_to_linux_no_comment_key() -> None:
    result = load_windows_to_linux()
    assert "_comment" not in result


def test_load_windows_to_linux_missing_file_returns_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mappings_mod, "_DATA_DIR", tmp_path)
    assert load_windows_to_linux() == {}


def test_load_windows_to_linux_invalid_json_returns_empty(monkeypatch, tmp_path) -> None:
    (tmp_path / "windows_to_linux_mapping.json").write_text("{ bad json", encoding="utf-8")
    monkeypatch.setattr(mappings_mod, "_DATA_DIR", tmp_path)
    assert load_windows_to_linux() == {}


def test_load_windows_to_linux_custom_data(monkeypatch, tmp_path) -> None:
    data = {
        "_comment": "ignored",
        "notepad++": {"linux_package": "gedit", "install_via": "apt", "category": "green"},
    }
    (tmp_path / "windows_to_linux_mapping.json").write_text(
        json.dumps(data), encoding="utf-8"
    )
    monkeypatch.setattr(mappings_mod, "_DATA_DIR", tmp_path)

    result = load_windows_to_linux()
    assert "notepad++" in result
    assert "_comment" not in result
    assert result["notepad++"]["linux_package"] == "gedit"


# ---------------------------------------------------------------------------
# load_opensource_alternatives
# ---------------------------------------------------------------------------


def test_load_opensource_alternatives_returns_dict() -> None:
    result = load_opensource_alternatives()
    assert isinstance(result, dict)


def test_load_opensource_alternatives_has_expected_keys() -> None:
    result = load_opensource_alternatives()
    assert "handbrake" in result
    assert "notepad++" in result


def test_load_opensource_alternatives_entry_has_required_fields() -> None:
    result = load_opensource_alternatives()
    entry = result["handbrake"]
    assert "alternative" in entry
    assert "linux_package" in entry
    assert "install_via" in entry


def test_load_opensource_alternatives_no_comment_key() -> None:
    result = load_opensource_alternatives()
    assert "_comment" not in result


def test_load_opensource_alternatives_missing_file_returns_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mappings_mod, "_DATA_DIR", tmp_path)
    assert load_opensource_alternatives() == {}
