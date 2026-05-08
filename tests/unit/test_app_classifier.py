"""Unit tests for windowstolinux.matcher.app_classifier."""

from __future__ import annotations

import pytest

from windowstolinux.matcher.app_classifier import (
    _classify_one,
    _flathub_id_plausible,
    _from_alternatives,
    _from_flathub,
    _from_repology,
    _from_static_mapping,
    _red_verdict,
    classify_all,
    classify_app,
)
from windowstolinux.models import WindowsApp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _app(name: str, publisher: str | None = None) -> WindowsApp:
    return WindowsApp(name=name, publisher=publisher)


def _empty_mapping() -> dict[str, dict]:
    return {}


def _mapping(*args: tuple[str, dict]) -> dict[str, dict]:
    return dict(args)


# ---------------------------------------------------------------------------
# _flathub_id_plausible
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("query, app_id, expected", [
    ("gimp", "org.gimp.GIMP", True),
    ("vlc media player", "org.videolan.VLC", True),
    ("mozilla firefox", "org.mozilla.firefox", True),
    ("spotify", "com.spotify.Client", True),
    ("adobe photoshop", "org.gimp.GIMP", False),       # "photoshop" not in ID
    ("microsoft word", "org.libreoffice.LibreOffice", False),  # "word" not in ID
    ("adobe premiere", "org.kde.kdenlive", False),
    ("x", "org.x.App", False),                         # query too short to match (len <= 2)
    ("", "org.gimp.GIMP", False),                      # empty query
])
def test_flathub_id_plausible(query: str, app_id: str, expected: bool) -> None:
    assert _flathub_id_plausible(query, app_id) is expected


# ---------------------------------------------------------------------------
# _from_static_mapping
# ---------------------------------------------------------------------------


def test_from_static_mapping_hit() -> None:
    app = _app("VLC media player")
    mapping = {"vlc media player": {"category": "green", "linux_package": "vlc", "install_via": "apt"}}
    result = _from_static_mapping(app, "vlc media player", mapping)
    assert result is not None
    assert result.category == "green"
    assert result.linux_package == "vlc"
    assert result.install_via == "apt"
    assert result.note is None


def test_from_static_mapping_with_note() -> None:
    app = _app("Microsoft Office")
    mapping = {
        "microsoft office": {
            "category": "yellow",
            "linux_package": "libreoffice",
            "install_via": "apt",
            "note": "LibreOffice als Alternative",
        }
    }
    result = _from_static_mapping(app, "microsoft office", mapping)
    assert result is not None
    assert result.note == "LibreOffice als Alternative"


def test_from_static_mapping_miss() -> None:
    assert _from_static_mapping(_app("Unknown App"), "unknown app", {}) is None


def test_from_static_mapping_red_without_package() -> None:
    app = _app("WinApp")
    mapping = {"winapp": {"category": "red"}}
    result = _from_static_mapping(app, "winapp", mapping)
    assert result is not None
    assert result.category == "red"
    assert result.linux_package is None
    assert result.install_via is None


def test_from_static_mapping_invalid_entry_returns_none() -> None:
    # linux_package set but install_via missing -> ValidationError inside
    app = _app("BadApp")
    mapping = {"badapp": {"category": "green", "linux_package": "something"}}
    result = _from_static_mapping(app, "badapp", mapping)
    assert result is None


def test_from_static_mapping_missing_category_returns_none() -> None:
    app = _app("BadApp")
    mapping = {"badapp": {"linux_package": "something", "install_via": "apt"}}
    result = _from_static_mapping(app, "badapp", mapping)
    assert result is None


# ---------------------------------------------------------------------------
# _from_repology
# ---------------------------------------------------------------------------


def test_from_repology_hit(mocker) -> None:
    mocker.patch("windowstolinux.matcher.app_classifier.repology.lookup", return_value="vlc")
    result = _from_repology(_app("VLC"), "vlc")
    assert result is not None
    assert result.category == "green"
    assert result.linux_package == "vlc"
    assert result.install_via == "apt"


def test_from_repology_miss(mocker) -> None:
    mocker.patch("windowstolinux.matcher.app_classifier.repology.lookup", return_value=None)
    assert _from_repology(_app("Unknown"), "unknown") is None


def test_from_repology_uses_lowercased_name(mocker) -> None:
    mock_lookup = mocker.patch(
        "windowstolinux.matcher.app_classifier.repology.lookup", return_value=None
    )
    _from_repology(_app("VLC"), "vlc")  # name already lowercased before call
    mock_lookup.assert_called_once_with("vlc")


# ---------------------------------------------------------------------------
# _from_flathub
# ---------------------------------------------------------------------------


def test_from_flathub_plausible_hit(mocker) -> None:
    mocker.patch(
        "windowstolinux.matcher.app_classifier.flathub.search",
        return_value="org.gimp.GIMP",
    )
    result = _from_flathub(_app("GIMP"), "gimp")
    assert result is not None
    assert result.category == "green"
    assert result.linux_package == "org.gimp.GIMP"
    assert result.install_via == "flatpak"


def test_from_flathub_implausible_result_rejected(mocker) -> None:
    # Flathub returns GIMP for a Photoshop query - should be rejected
    mocker.patch(
        "windowstolinux.matcher.app_classifier.flathub.search",
        return_value="org.gimp.GIMP",
    )
    result = _from_flathub(_app("Adobe Photoshop"), "adobe photoshop")
    assert result is None


def test_from_flathub_no_result(mocker) -> None:
    mocker.patch("windowstolinux.matcher.app_classifier.flathub.search", return_value=None)
    assert _from_flathub(_app("Obscure Tool"), "obscure tool") is None


def test_from_flathub_spotify_match(mocker) -> None:
    mocker.patch(
        "windowstolinux.matcher.app_classifier.flathub.search",
        return_value="com.spotify.Client",
    )
    result = _from_flathub(_app("Spotify"), "spotify")
    assert result is not None
    assert result.linux_package == "com.spotify.Client"


# ---------------------------------------------------------------------------
# _from_alternatives
# ---------------------------------------------------------------------------


def test_from_alternatives_hit() -> None:
    app = _app("Adobe Premiere")
    alternatives = {
        "adobe premiere": {
            "alternative": "Kdenlive",
            "linux_package": "org.kde.kdenlive",
            "install_via": "flatpak",
        }
    }
    result = _from_alternatives(app, "adobe premiere", alternatives)
    assert result is not None
    assert result.category == "yellow"
    assert result.linux_package == "org.kde.kdenlive"
    assert result.install_via == "flatpak"
    assert "Kdenlive" in result.note


def test_from_alternatives_miss() -> None:
    assert _from_alternatives(_app("Unknown"), "unknown", {}) is None


def test_from_alternatives_note_contains_alternative_name() -> None:
    alternatives = {
        "adobe illustrator": {
            "alternative": "Inkscape",
            "linux_package": "org.inkscape.Inkscape",
            "install_via": "flatpak",
        }
    }
    result = _from_alternatives(_app("Adobe Illustrator"), "adobe illustrator", alternatives)
    assert result is not None
    assert "Inkscape" in result.note


def test_from_alternatives_invalid_entry_returns_none() -> None:
    # linux_package without install_via -> ValidationError
    alternatives = {
        "buggy app": {
            "alternative": "Something",
            "linux_package": "something",
            # missing install_via
        }
    }
    result = _from_alternatives(_app("Buggy App"), "buggy app", alternatives)
    assert result is None


# ---------------------------------------------------------------------------
# _red_verdict
# ---------------------------------------------------------------------------


def test_red_verdict_category() -> None:
    result = _red_verdict(_app("Windows-Only Tool"))
    assert result.category == "red"
    assert result.linux_package is None
    assert result.install_via is None


def test_red_verdict_note_mentions_wine() -> None:
    result = _red_verdict(_app("Windows-Only Tool"))
    assert result.note is not None
    assert "Wine" in result.note


# ---------------------------------------------------------------------------
# _classify_one - priority ordering
# ---------------------------------------------------------------------------


def test_classify_one_static_mapping_takes_priority(mocker) -> None:
    repology_mock = mocker.patch("windowstolinux.matcher.app_classifier.repology.lookup")
    flathub_mock = mocker.patch("windowstolinux.matcher.app_classifier.flathub.search")

    mapping = {"vlc media player": {"category": "green", "linux_package": "vlc", "install_via": "apt"}}
    result = _classify_one(_app("VLC media player"), mapping, {})

    assert result.category == "green"
    assert result.linux_package == "vlc"
    repology_mock.assert_not_called()
    flathub_mock.assert_not_called()


def test_classify_one_repology_before_flathub(mocker) -> None:
    mocker.patch("windowstolinux.matcher.app_classifier.repology.lookup", return_value="vlc")
    flathub_mock = mocker.patch("windowstolinux.matcher.app_classifier.flathub.search")

    result = _classify_one(_app("VLC"), _empty_mapping(), {})

    assert result.install_via == "apt"
    flathub_mock.assert_not_called()


def test_classify_one_flathub_before_alternatives(mocker) -> None:
    mocker.patch("windowstolinux.matcher.app_classifier.repology.lookup", return_value=None)
    mocker.patch(
        "windowstolinux.matcher.app_classifier.flathub.search",
        return_value="com.spotify.Client",
    )

    alternatives = {"spotify": {"alternative": "Lollypop", "linux_package": "lollypop", "install_via": "apt"}}
    result = _classify_one(_app("Spotify"), _empty_mapping(), alternatives)

    assert result.install_via == "flatpak"
    assert result.linux_package == "com.spotify.Client"


def test_classify_one_falls_through_to_alternatives(mocker) -> None:
    mocker.patch("windowstolinux.matcher.app_classifier.repology.lookup", return_value=None)
    mocker.patch("windowstolinux.matcher.app_classifier.flathub.search", return_value=None)

    alternatives = {
        "adobe premiere": {
            "alternative": "Kdenlive",
            "linux_package": "org.kde.kdenlive",
            "install_via": "flatpak",
        }
    }
    result = _classify_one(_app("Adobe Premiere"), _empty_mapping(), alternatives)

    assert result.category == "yellow"


def test_classify_one_red_when_all_miss(mocker) -> None:
    mocker.patch("windowstolinux.matcher.app_classifier.repology.lookup", return_value=None)
    mocker.patch("windowstolinux.matcher.app_classifier.flathub.search", return_value=None)

    result = _classify_one(_app("SomeWindowsOnlyTool"), _empty_mapping(), {})

    assert result.category == "red"


def test_classify_one_implausible_flathub_falls_through(mocker) -> None:
    mocker.patch("windowstolinux.matcher.app_classifier.repology.lookup", return_value=None)
    # Flathub returns GIMP for "Adobe Photoshop" (implausible)
    mocker.patch(
        "windowstolinux.matcher.app_classifier.flathub.search",
        return_value="org.gimp.GIMP",
    )

    result = _classify_one(_app("Adobe Photoshop"), _empty_mapping(), {})

    # Falls through to red because there's no alternatives entry either
    assert result.category == "red"


# ---------------------------------------------------------------------------
# classify_app / classify_all
# ---------------------------------------------------------------------------


def test_classify_app_returns_single_match(mocker) -> None:
    mocker.patch("windowstolinux.matcher.app_classifier.mappings.load_windows_to_linux",
                 return_value={"firefox": {"category": "green", "linux_package": "firefox", "install_via": "apt"}})
    mocker.patch("windowstolinux.matcher.app_classifier.mappings.load_opensource_alternatives",
                 return_value={})

    result = classify_app(_app("Firefox"))
    assert result.category == "green"


def test_classify_all_loads_mappings_once(mocker) -> None:
    load_mapping = mocker.patch(
        "windowstolinux.matcher.app_classifier.mappings.load_windows_to_linux",
        return_value={},
    )
    mocker.patch("windowstolinux.matcher.app_classifier.mappings.load_opensource_alternatives",
                 return_value={})
    mocker.patch("windowstolinux.matcher.app_classifier.repology.lookup", return_value=None)
    mocker.patch("windowstolinux.matcher.app_classifier.flathub.search", return_value=None)

    apps = [_app("App A"), _app("App B"), _app("App C")]
    results = classify_all(apps)

    assert len(results) == 3
    load_mapping.assert_called_once()  # not three times


def test_classify_all_preserves_order(mocker) -> None:
    mocker.patch("windowstolinux.matcher.app_classifier.mappings.load_windows_to_linux",
                 return_value={})
    mocker.patch("windowstolinux.matcher.app_classifier.mappings.load_opensource_alternatives",
                 return_value={})
    mocker.patch("windowstolinux.matcher.app_classifier.repology.lookup", return_value=None)
    mocker.patch("windowstolinux.matcher.app_classifier.flathub.search", return_value=None)

    apps = [_app("Zoom"), _app("Slack"), _app("Teams")]
    results = classify_all(apps)

    assert [r.windows_app.name for r in results] == ["Zoom", "Slack", "Teams"]


def test_classify_all_empty_list(mocker) -> None:
    mocker.patch("windowstolinux.matcher.app_classifier.mappings.load_windows_to_linux",
                 return_value={})
    mocker.patch("windowstolinux.matcher.app_classifier.mappings.load_opensource_alternatives",
                 return_value={})

    assert classify_all([]) == []
