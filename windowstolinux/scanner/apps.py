"""Installierte Programme aus der Windows-Registry auslesen.

Durchläuft alle drei Uninstall-Hives (HKLM 64-Bit, HKLM 32-Bit, HKCU)
und filtert Systemkomponenten, Windows-Updates und Runtime-Bibliotheken
heraus, die für den Migrationsbericht nicht relevant sind.
"""

from __future__ import annotations

import logging
from typing import Iterator

from windowstolinux.models import WindowsApp
from windowstolinux.normalizer import normalize_app_name

logger = logging.getLogger(__name__)

# HKEY-Konstanten als Integer, damit dieses Modul auch auf Nicht-Windows importierbar ist.
# Werte sind identisch mit winreg.HKEY_LOCAL_MACHINE / HKEY_CURRENT_USER.
_HKEY_LOCAL_MACHINE = 0x80000002
_HKEY_CURRENT_USER  = 0x80000001

_UNINSTALL_PATH     = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
_UNINSTALL_PATH_WOW = r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"

_HIVES: list[tuple[int, str]] = [
    (_HKEY_LOCAL_MACHINE, _UNINSTALL_PATH),
    (_HKEY_LOCAL_MACHINE, _UNINSTALL_PATH_WOW),
    (_HKEY_CURRENT_USER,  _UNINSTALL_PATH),
]

_VALUE_NAMES = (
    "DisplayName",
    "Publisher",
    "DisplayVersion",
    "SystemComponent",
    "ReleaseType",
    "ParentKeyName",
)

# Nur aufnehmen, was nicht bereits durch SystemComponent=1 oder ReleaseType gefiltert wird.
_BLACKLISTED_SUBSTRINGS: frozenset[str] = frozenset({
    "microsoft visual c++",
    "microsoft .net",
    "windows software development kit",
    "windows driver kit",
    "microsoft update health tools",
    "windows assessment and deployment kit",
    "windows malicious software removal tool",
    "windows pc health check",
})


def scan_installed_apps() -> list[WindowsApp]:
    """Gibt alle Nutzer-installierten Programme aus der Registry zurück.

    Durchläuft alle drei Uninstall-Hives, filtert Systemkomponenten und
    dedupliziert Einträge die in mehreren Hives vorkommen.
    Ergebnis ist alphabetisch sortiert.
    """
    seen: dict[str, WindowsApp] = {}

    for entry in _iter_hive_entries():
        app = _entry_to_app(entry)
        if app is None:
            continue
        key = normalize_app_name(app.name)
        if key not in seen:
            seen[key] = app

    return sorted(seen.values(), key=lambda a: a.name.lower())


def _entry_to_app(entry: dict[str, str]) -> WindowsApp | None:
    name = entry.get("DisplayName", "").strip()
    if not name:
        return None
    if _is_system_component(entry):
        return None
    if _is_blacklisted(name):
        return None

    publisher = entry.get("Publisher", "").strip() or None
    version   = entry.get("DisplayVersion", "").strip() or None
    return WindowsApp(name=name, publisher=publisher, version=version)


def _is_system_component(entry: dict[str, str]) -> bool:
    if entry.get("SystemComponent") == "1":
        return True
    if "ReleaseType" in entry:      # Windows-Updates und Hotfixes
        return True
    if "ParentKeyName" in entry:    # Unterkomponente eines anderen Installers
        return True
    return False


def _is_blacklisted(name: str) -> bool:
    name_lower = name.lower()
    return any(pattern in name_lower for pattern in _BLACKLISTED_SUBSTRINGS)


def _iter_hive_entries() -> Iterator[dict[str, str]]:
    """Liefert rohe Registry-Werte aus allen drei Uninstall-Hives.

    Hives ohne Zugriffsberechtigung werden stillschweigend übersprungen.
    Auf Nicht-Windows-Systemen (kein winreg) wird nichts geliefert.
    """
    try:
        import winreg  # noqa: PLC0415
    except ImportError:
        logger.warning("winreg nicht verfügbar, App-Scan erfordert Windows")
        return

    for hive, path in _HIVES:
        try:
            with winreg.OpenKey(hive, path) as root:
                index = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(root, index)
                        try:
                            with winreg.OpenKey(root, subkey_name) as sub:
                                yield _read_key_values(winreg, sub)
                        except OSError:
                            pass
                        index += 1
                    except OSError:
                        break  # keine weiteren Unterschlüssel in diesem Hive
        except OSError:
            logger.debug(f"Registry-Pfad nicht zugänglich: {path}")


def _read_key_values(winreg_mod: object, key: object) -> dict[str, str]:
    """Liest die relevanten Werte aus einem geöffneten Registry-Schlüssel.

    winreg_mod wird als Parameter übergeben, damit er in Tests mockbar ist.
    Nicht vorhandene Werte werden einfach weggelassen.
    """
    values: dict[str, str] = {}
    for name in _VALUE_NAMES:
        try:
            value, _ = winreg_mod.QueryValueEx(key, name)  # type: ignore[attr-defined]
            values[name] = str(value)
        except OSError:
            pass
    return values
