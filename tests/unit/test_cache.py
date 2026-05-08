"""Unit tests for windowstolinux.resolver.cache."""

from __future__ import annotations

import time

import pytest

import windowstolinux.resolver.cache as cache_mod
from windowstolinux.resolver.cache import get, set


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Point every test at a fresh temporary cache DB."""
    monkeypatch.setenv("WINDOWSTOLINUX_CACHE_PATH", str(tmp_path / "test_cache.db"))


# ---------------------------------------------------------------------------
# get / set round-trip
# ---------------------------------------------------------------------------


def test_get_returns_none_for_missing_key() -> None:
    assert get("nonexistent") is None


def test_set_and_get_round_trip() -> None:
    set("repology:vlc", "vlc")
    assert get("repology:vlc") == "vlc"


def test_set_and_get_empty_sentinel() -> None:
    set("repology:unknown", "")
    # Empty string is a valid cached "not found" - returned as-is
    assert get("repology:unknown") == ""


def test_set_overwrites_existing() -> None:
    set("key", "first")
    set("key", "second")
    assert get("key") == "second"


# ---------------------------------------------------------------------------
# TTL / stale
# ---------------------------------------------------------------------------


def test_get_returns_none_for_expired_entry(monkeypatch) -> None:
    # Store entry, then pretend 8 days have passed
    set("key", "value")
    monkeypatch.setattr(cache_mod, "_TTL_SECONDS", 0)
    # TTL of 0 means everything older than "now" is expired
    assert get("key") is None


def test_get_stale_returns_expired_entry(monkeypatch) -> None:
    set("key", "old_value")
    monkeypatch.setattr(cache_mod, "_TTL_SECONDS", 0)
    assert get("key", allow_stale=True) == "old_value"


def test_get_stale_returns_none_for_completely_missing_key() -> None:
    assert get("missing", allow_stale=True) is None


def test_fresh_entry_not_affected_by_allow_stale() -> None:
    set("key", "value")
    assert get("key", allow_stale=False) == "value"
    assert get("key", allow_stale=True) == "value"


# ---------------------------------------------------------------------------
# DB path creation
# ---------------------------------------------------------------------------


def test_cache_creates_parent_directories(tmp_path, monkeypatch) -> None:
    nested = tmp_path / "a" / "b" / "c" / "cache.db"
    monkeypatch.setenv("WINDOWSTOLINUX_CACHE_PATH", str(nested))
    set("x", "y")
    assert nested.exists()


# ---------------------------------------------------------------------------
# get_cache_path
# ---------------------------------------------------------------------------


def test_get_cache_path_uses_env_var(tmp_path, monkeypatch) -> None:
    target = tmp_path / "custom.db"
    monkeypatch.setenv("WINDOWSTOLINUX_CACHE_PATH", str(target))
    assert cache_mod.get_cache_path() == target


def test_get_cache_path_falls_back_to_localappdata(monkeypatch) -> None:
    monkeypatch.delenv("WINDOWSTOLINUX_CACHE_PATH", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", "C:\\Users\\Test\\AppData\\Local")
    path = cache_mod.get_cache_path()
    assert "WindowsToLinux" in str(path)
    assert path.name == "cache.db"


def test_get_cache_path_no_localappdata_uses_home_fallback(monkeypatch) -> None:
    monkeypatch.delenv("WINDOWSTOLINUX_CACHE_PATH", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    path = cache_mod.get_cache_path()
    assert "WindowsToLinux" in str(path)


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------


def test_get_returns_none_on_unreadable_db(tmp_path, monkeypatch) -> None:
    # Point to a file that is not a valid SQLite DB
    bad_db = tmp_path / "bad.db"
    bad_db.write_text("not a sqlite db", encoding="utf-8")
    monkeypatch.setenv("WINDOWSTOLINUX_CACHE_PATH", str(bad_db))
    # Should not raise
    assert get("key") is None


def test_set_does_not_raise_on_unreadable_db(tmp_path, monkeypatch) -> None:
    bad_db = tmp_path / "bad.db"
    bad_db.write_text("not a sqlite db", encoding="utf-8")
    monkeypatch.setenv("WINDOWSTOLINUX_CACHE_PATH", str(bad_db))
    # Should not raise
    set("key", "value")
