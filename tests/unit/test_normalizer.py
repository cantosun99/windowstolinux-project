"""Unit tests for windowstolinux.normalizer."""

from __future__ import annotations

import pytest

from windowstolinux.normalizer import find_in_mapping, normalize_app_name


# ---------------------------------------------------------------------------
# normalize_app_name - real-world Windows Registry names
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [
    # Version numbers stripped
    ("VLC media player 3.0.20",             "vlc media player"),
    ("GIMP 2.10.36",                        "gimp"),
    ("Inkscape 1.3.2",                      "inkscape"),
    ("Python 3.12.0 (64-bit)",              "python"),
    # Architecture tags stripped
    ("7-Zip 23.01 (x64)",                   "7-zip"),
    ("Notepad++ (64-bit x86)",              "notepad++"),
    ("Adobe Acrobat DC (64-bit)",           "adobe acrobat dc"),
    # Locale codes stripped
    ("Mozilla Firefox 123.0.1 (x64 de)",    "mozilla firefox"),
    ("Mozilla Firefox (x64 de)",            "mozilla firefox"),
    # Locale suffix after dash stripped
    ("Microsoft Office Plus 2019 - de-de",  "microsoft office plus"),
    ("Something App 2022 - en",             "something app"),
    # Year-like numbers stripped
    ("Microsoft Office Professional Plus 2019", "microsoft office professional plus"),
    ("AutoCAD 2024",                        "autocad"),
    # Build number remnants stripped
    ("Zoom 6.2.3 (44643)",                  "zoom"),
    # No-op cases (nothing to strip)
    ("Google Chrome",                       "google chrome"),
    ("Spotify",                             "spotify"),
    ("Microsoft OneDrive",                  "microsoft onedrive"),
    # Case normalised
    ("VLC Media Player",                    "vlc media player"),
    # Natural-language parens preserved
    ("Microsoft Teams (work or school)",    "microsoft teams (work or school)"),
    # Trailing/leading whitespace handled
    ("  Firefox  ",                         "firefox"),
])
def test_normalize_app_name(raw: str, expected: str) -> None:
    assert normalize_app_name(raw) == expected


def test_normalize_preserves_plus_sign() -> None:
    assert normalize_app_name("Notepad++") == "notepad++"


def test_normalize_preserves_hyphen_in_name() -> None:
    assert normalize_app_name("7-Zip") == "7-zip"


def test_normalize_empty_string() -> None:
    assert normalize_app_name("") == ""


def test_normalize_only_version() -> None:
    assert normalize_app_name("3.0.20") == ""


# ---------------------------------------------------------------------------
# find_in_mapping - exact match
# ---------------------------------------------------------------------------


def test_find_exact_match() -> None:
    mapping = {"firefox": {"category": "green", "linux_package": "firefox", "install_via": "apt"}}
    result = find_in_mapping("firefox", mapping)
    assert result is not None
    assert result["linux_package"] == "firefox"


def test_find_exact_match_not_found() -> None:
    assert find_in_mapping("unknown app", {}) is None


def test_find_exact_preferred_over_prefix() -> None:
    mapping = {
        "microsoft office":                    {"category": "yellow", "id": "office"},
        "microsoft office professional plus":  {"category": "yellow", "id": "office-pro"},
    }
    result = find_in_mapping("microsoft office professional plus", mapping)
    assert result["id"] == "office-pro"


# ---------------------------------------------------------------------------
# find_in_mapping - prefix match
# ---------------------------------------------------------------------------


def test_find_prefix_match() -> None:
    mapping = {"microsoft office": {"category": "yellow", "linux_package": "libreoffice", "install_via": "apt"}}
    result = find_in_mapping("microsoft office professional plus", mapping)
    assert result is not None
    assert result["linux_package"] == "libreoffice"


def test_find_prefix_longest_key_wins() -> None:
    mapping = {
        "adobe":          {"id": "adobe-base"},
        "adobe acrobat":  {"id": "adobe-acrobat"},
    }
    result = find_in_mapping("adobe acrobat reader dc", mapping)
    assert result["id"] == "adobe-acrobat"


def test_find_prefix_requires_word_boundary() -> None:
    # "vlc" should NOT match "vlctools extra" as a prefix of "vlctools"
    mapping = {"vlc": {"id": "vlc"}}
    assert find_in_mapping("vlctools extra", mapping) is None


def test_find_prefix_exact_length_handled_by_exact_match() -> None:
    mapping = {"firefox": {"id": "ff"}}
    assert find_in_mapping("firefox", mapping) is not None


def test_find_returns_none_when_only_partial_word_match() -> None:
    mapping = {"fire": {"id": "fire"}}
    # "firefox" starts with "fire" but next char is "f" not " "
    assert find_in_mapping("firefox", mapping) is None


# ---------------------------------------------------------------------------
# Integration: normalize + find round-trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw_name, key_in_mapping", [
    ("VLC media player 3.0.20",             "vlc media player"),
    ("7-Zip 23.01 (x64)",                   "7-zip"),
    ("Mozilla Firefox 123.0 (x64 de)",      "mozilla firefox"),
    ("Microsoft Office Professional Plus 2019 - de-de", "microsoft office"),
    ("Adobe Acrobat DC (64-bit)",           "adobe acrobat"),
    ("GIMP 2.10.36",                        "gimp"),
])
def test_normalize_then_find(raw_name: str, key_in_mapping: str) -> None:
    mapping = {key_in_mapping: {"category": "green", "linux_package": "pkg", "install_via": "apt"}}
    norm = normalize_app_name(raw_name)
    result = find_in_mapping(norm, mapping)
    assert result is not None, f"'{raw_name}' -> '{norm}' did not match key '{key_in_mapping}'"
