"""Unit tests for windowstolinux.scanner.apps."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from windowstolinux.scanner.apps import (
    _entry_to_app,
    _is_blacklisted,
    _is_system_component,
    _iter_hive_entries,
    _read_key_values,
    scan_installed_apps,
)


# ---------------------------------------------------------------------------
# _is_system_component
# ---------------------------------------------------------------------------


def test_system_component_flag() -> None:
    assert _is_system_component({"DisplayName": "X", "SystemComponent": "1"}) is True


def test_system_component_flag_zero_is_not_filtered() -> None:
    assert _is_system_component({"DisplayName": "X", "SystemComponent": "0"}) is False


def test_system_component_release_type() -> None:
    assert _is_system_component({"DisplayName": "X", "ReleaseType": "Update"}) is True


def test_system_component_parent_key() -> None:
    assert _is_system_component({"DisplayName": "X", "ParentKeyName": "SomeParent"}) is True


def test_system_component_normal_app() -> None:
    assert _is_system_component({"DisplayName": "VLC media player", "Publisher": "VideoLAN"}) is False


# ---------------------------------------------------------------------------
# _is_blacklisted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", [
    "Microsoft Visual C++ 2019 Redistributable (x64)",
    "Microsoft Visual C++ 2013 Redistributable (x86)",
    "Microsoft .NET Framework 4.8",
    "Microsoft .NET Runtime 8.0.1",
    "Windows Software Development Kit - Windows 11",
    "Windows Driver Kit - Windows 11",
    "Microsoft Update Health Tools",
    "Windows Assessment and Deployment Kit",
    "Windows Malicious Software Removal Tool",
    "Windows PC Health Check",
])
def test_is_blacklisted_matches(name: str) -> None:
    assert _is_blacklisted(name) is True


@pytest.mark.parametrize("name", [
    "VLC media player",
    "Microsoft Edge",
    "Microsoft Office",
    "Microsoft OneDrive",
    "Microsoft Visual Studio 2022",  # IDE, not runtime
    "7-Zip 23.01",
    "Google Chrome",
    "Spotify",
])
def test_is_blacklisted_does_not_match(name: str) -> None:
    assert _is_blacklisted(name) is False


def test_is_blacklisted_case_insensitive() -> None:
    assert _is_blacklisted("MICROSOFT VISUAL C++ 2019") is True
    assert _is_blacklisted("microsoft visual c++ 2019") is True


# ---------------------------------------------------------------------------
# _entry_to_app
# ---------------------------------------------------------------------------


def test_entry_to_app_full() -> None:
    entry = {"DisplayName": "VLC media player", "Publisher": "VideoLAN", "DisplayVersion": "3.0.20"}
    app = _entry_to_app(entry)
    assert app is not None
    assert app.name == "VLC media player"
    assert app.publisher == "VideoLAN"
    assert app.version == "3.0.20"


def test_entry_to_app_minimal() -> None:
    app = _entry_to_app({"DisplayName": "Notepad++"})
    assert app is not None
    assert app.name == "Notepad++"
    assert app.publisher is None
    assert app.version is None


def test_entry_to_app_no_name_returns_none() -> None:
    assert _entry_to_app({}) is None
    assert _entry_to_app({"DisplayName": ""}) is None
    assert _entry_to_app({"DisplayName": "   "}) is None


def test_entry_to_app_strips_whitespace() -> None:
    entry = {"DisplayName": "  VLC  ", "Publisher": "  VideoLAN  ", "DisplayVersion": "  3.0  "}
    app = _entry_to_app(entry)
    assert app is not None
    assert app.name == "VLC"
    assert app.publisher == "VideoLAN"
    assert app.version == "3.0"


def test_entry_to_app_empty_publisher_becomes_none() -> None:
    app = _entry_to_app({"DisplayName": "VLC", "Publisher": ""})
    assert app is not None
    assert app.publisher is None


def test_entry_to_app_system_component_filtered() -> None:
    assert _entry_to_app({"DisplayName": "Some Runtime", "SystemComponent": "1"}) is None


def test_entry_to_app_release_type_filtered() -> None:
    assert _entry_to_app({"DisplayName": "KB5034441", "ReleaseType": "Update"}) is None


def test_entry_to_app_parent_key_filtered() -> None:
    assert _entry_to_app({"DisplayName": "Sub Component", "ParentKeyName": "MainApp"}) is None


def test_entry_to_app_blacklisted_filtered() -> None:
    assert _entry_to_app({"DisplayName": "Microsoft Visual C++ 2019 Redistributable"}) is None


# ---------------------------------------------------------------------------
# _read_key_values
# ---------------------------------------------------------------------------


def test_read_key_values_reads_present_values() -> None:
    mock_winreg = MagicMock()
    mock_key = MagicMock()

    def query_val(key, name: str):
        data = {
            "DisplayName": ("VLC media player", 1),
            "Publisher": ("VideoLAN", 1),
            "DisplayVersion": ("3.0.20", 1),
        }
        if name in data:
            return data[name]
        raise OSError("not found")

    mock_winreg.QueryValueEx.side_effect = query_val

    result = _read_key_values(mock_winreg, mock_key)

    assert result["DisplayName"] == "VLC media player"
    assert result["Publisher"] == "VideoLAN"
    assert result["DisplayVersion"] == "3.0.20"
    assert "SystemComponent" not in result
    assert "ReleaseType" not in result


def test_read_key_values_coerces_to_str() -> None:
    mock_winreg = MagicMock()

    def query_val(key, name: str):
        if name == "SystemComponent":
            return (1, 4)  # REG_DWORD returns int
        raise OSError("not found")

    mock_winreg.QueryValueEx.side_effect = query_val

    result = _read_key_values(mock_winreg, MagicMock())

    assert result["SystemComponent"] == "1"


# ---------------------------------------------------------------------------
# _iter_hive_entries
# ---------------------------------------------------------------------------


def test_iter_hive_entries_no_winreg(mocker) -> None:
    mocker.patch.dict("sys.modules", {"winreg": None})  # type: ignore[dict-item]
    assert list(_iter_hive_entries()) == []


def test_iter_hive_entries_import_error(mocker) -> None:
    # Simulate winreg not being installed at all (not just None in sys.modules)
    original = __builtins__

    def fake_import(name, *args, **kwargs):
        if name == "winreg":
            raise ImportError("No module named 'winreg'")
        return original.__import__(name, *args, **kwargs) if hasattr(original, "__import__") else __import__(name, *args, **kwargs)

    mocker.patch("builtins.__import__", side_effect=fake_import)
    assert list(_iter_hive_entries()) == []


def _build_winreg_mock(display_name: str = "VLC media player") -> MagicMock:
    """Return a mock winreg module that yields one entry per hive."""
    mock_winreg = MagicMock()

    root_mock = MagicMock()
    sub_mock = MagicMock()

    def open_key(hive_or_key, name):
        cm = MagicMock()
        if isinstance(hive_or_key, int):
            cm.__enter__ = MagicMock(return_value=root_mock)
        else:
            cm.__enter__ = MagicMock(return_value=sub_mock)
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    mock_winreg.OpenKey.side_effect = open_key

    def enum_key(key, index):
        if index == 0:
            return "APP-GUID-1234"
        raise OSError("no more keys")

    mock_winreg.EnumKey.side_effect = enum_key

    def query_val(key, name: str):
        if name == "DisplayName":
            return (display_name, 1)
        raise OSError("not found")

    mock_winreg.QueryValueEx.side_effect = query_val
    return mock_winreg


def test_iter_hive_entries_yields_one_entry_per_hive(mocker) -> None:
    mock_winreg = _build_winreg_mock("VLC media player")
    mocker.patch.dict("sys.modules", {"winreg": mock_winreg})

    entries = list(_iter_hive_entries())

    assert len(entries) == 3  # one per hive
    assert all(e["DisplayName"] == "VLC media player" for e in entries)


def test_iter_hive_entries_skips_inaccessible_hive(mocker) -> None:
    mock_winreg = MagicMock()

    call_count = [0]

    def open_key(hive_or_key, name):
        if isinstance(hive_or_key, int):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("access denied")
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock())
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    mock_winreg.OpenKey.side_effect = open_key
    mock_winreg.EnumKey.side_effect = OSError("no keys")
    mocker.patch.dict("sys.modules", {"winreg": mock_winreg})

    entries = list(_iter_hive_entries())

    assert entries == []  # second and third hive have no entries


def test_iter_hive_entries_skips_unreadable_subkey(mocker) -> None:
    """A subkey that raises OSError on OpenKey should be skipped, not crash."""
    mock_winreg = MagicMock()
    root_mock = MagicMock()

    def open_key(hive_or_key, name):
        if isinstance(hive_or_key, int):
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=root_mock)
            cm.__exit__ = MagicMock(return_value=False)
            return cm
        raise OSError("permission denied on subkey")

    mock_winreg.OpenKey.side_effect = open_key

    def enum_key(key, index):
        if index == 0:
            return "LOCKED-GUID"
        raise OSError("no more")

    mock_winreg.EnumKey.side_effect = enum_key
    mocker.patch.dict("sys.modules", {"winreg": mock_winreg})

    entries = list(_iter_hive_entries())

    assert entries == []


# ---------------------------------------------------------------------------
# scan_installed_apps (integration: mocks _iter_hive_entries)
# ---------------------------------------------------------------------------


def _make_entry(name: str, publisher: str = "", version: str = "", **extra: str) -> dict[str, str]:
    e: dict[str, str] = {"DisplayName": name}
    if publisher:
        e["Publisher"] = publisher
    if version:
        e["DisplayVersion"] = version
    e.update(extra)
    return e


def test_scan_installed_apps_returns_user_apps(mocker) -> None:
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=iter([
            _make_entry("VLC media player", "VideoLAN", "3.0.20"),
            _make_entry("Firefox", "Mozilla", "123.0"),
        ]),
    )

    apps = scan_installed_apps()

    assert len(apps) == 2
    assert apps[0].name == "Firefox"  # sorted alphabetically
    assert apps[1].name == "VLC media player"


def test_scan_installed_apps_deduplicates(mocker) -> None:
    # Same app in HKLM and HKCU
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=iter([
            _make_entry("VLC media player", "VideoLAN"),
            _make_entry("VLC media player", "VideoLAN"),
            _make_entry("VLC media player", "VideoLAN"),
        ]),
    )

    apps = scan_installed_apps()

    assert len(apps) == 1
    assert apps[0].name == "VLC media player"


def test_scan_installed_apps_dedup_case_insensitive(mocker) -> None:
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=iter([
            _make_entry("vlc media player"),
            _make_entry("VLC Media Player"),
        ]),
    )

    apps = scan_installed_apps()

    assert len(apps) == 1


def test_scan_installed_apps_filters_system_components(mocker) -> None:
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=iter([
            _make_entry("VLC media player"),
            _make_entry("Microsoft Visual C++ 2019"),  # blacklisted
            _make_entry("Some Runtime", SystemComponent="1"),  # system component
            _make_entry("KB5034441", ReleaseType="Update"),  # update
            _make_entry("Sub Component", ParentKeyName="Parent"),  # sub-component
            _make_entry(""),  # no name
        ]),
    )

    apps = scan_installed_apps()

    assert len(apps) == 1
    assert apps[0].name == "VLC media player"


def test_scan_installed_apps_sorted_alphabetically(mocker) -> None:
    mocker.patch(
        "windowstolinux.scanner.apps._iter_hive_entries",
        return_value=iter([
            _make_entry("Zoom"),
            _make_entry("7-Zip"),
            _make_entry("Firefox"),
            _make_entry("Adobe Reader"),
        ]),
    )

    apps = scan_installed_apps()

    names = [a.name for a in apps]
    assert names == sorted(names, key=str.lower)


def test_scan_installed_apps_empty_registry(mocker) -> None:
    mocker.patch("windowstolinux.scanner.apps._iter_hive_entries", return_value=iter([]))

    assert scan_installed_apps() == []
