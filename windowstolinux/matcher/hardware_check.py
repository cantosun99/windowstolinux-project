"""Hardware-Bewertung gegen die Linux-Mint-Cinnamon-Mindestanforderungen.

Mindestanforderungen (Linux Mint 22 Cinnamon):
  - 64-Bit-Prozessor
  - 2 GB RAM (4 GB empfohlen)
  - 20 GB freier Speicherplatz (40 GB empfohlen)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from windowstolinux.models import HardwareInfo, HardwareVerdict, Status

logger = logging.getLogger(__name__)

RAM_RED_GB    = 2.0
RAM_YELLOW_GB = 4.0
DISK_RED_GB   = 20.0
DISK_YELLOW_GB = 40.0

_BLACKLIST_PATH = Path(__file__).parent.parent / "data" / "hardware_blacklist.json"

# Zuordnung von Hersteller-Namensteilstrings zur BIOS-Boot-Menü-Taste.
_BOOT_KEY_MAP: dict[str, str] = {
    "lenovo":   "F12",
    "dell":     "F12",
    "hp":       "F9",
    "hewlett":  "F9",
    "acer":     "F12",
    "asus":     "F8",
    "msi":      "F11",
    "samsung":  "F2",
    "toshiba":  "F12",
    "sony":     "F11",
    "fujitsu":  "F12",
    "gigabyte": "F12",
}


def check_hardware(hardware: HardwareInfo) -> HardwareVerdict:
    """Bewertet die Hardware und gibt ein farbiges Urteil mit Klartexthinweisen zurück."""
    cpu_status,  cpu_issues  = _check_cpu(hardware)
    ram_status,  ram_issues  = _check_ram(hardware.ram_gb)
    disk_status, disk_issues = _check_disk(hardware.disk_free_gb)
    blacklist_issues = _check_blacklist(hardware)

    overall = _overall_status(cpu_status, ram_status, disk_status)
    if blacklist_issues and overall == "green":
        overall = "yellow"

    return HardwareVerdict(
        overall=overall,
        cpu_status=cpu_status,
        ram_status=ram_status,
        disk_status=disk_status,
        issues=cpu_issues + ram_issues + disk_issues + blacklist_issues,
        boot_key_hint=_get_boot_key_hint(hardware.manufacturer),
    )


def _overall_status(*statuses: Status) -> Status:
    if "red" in statuses:
        return "red"
    if "yellow" in statuses:
        return "yellow"
    return "green"


def _check_cpu(hardware: HardwareInfo) -> tuple[Status, list[str]]:
    if not hardware.cpu_64bit:
        return "red", [
            "Ihr Prozessor ist 32-Bit. Linux Mint benötigt einen 64-Bit-Prozessor "
            "und kann auf diesem Gerät nicht installiert werden."
        ]
    return "green", []


def _check_ram(ram_gb: float) -> tuple[Status, list[str]]:
    if ram_gb < RAM_RED_GB:
        return "red", [
            f"Nur {ram_gb:.1f} GB Arbeitsspeicher vorhanden. "
            f"Linux Mint benötigt mindestens {RAM_RED_GB:.0f} GB."
        ]
    if ram_gb < RAM_YELLOW_GB:
        return "yellow", [
            f"{ram_gb:.1f} GB Arbeitsspeicher vorhanden. "
            f"Für einen flüssigen Betrieb werden {RAM_YELLOW_GB:.0f} GB empfohlen."
        ]
    return "green", []


def _check_disk(disk_free_gb: float) -> tuple[Status, list[str]]:
    if disk_free_gb < DISK_RED_GB:
        return "red", [
            f"Nur {disk_free_gb:.0f} GB freier Speicherplatz vorhanden. "
            f"Für die Installation werden mindestens {DISK_RED_GB:.0f} GB benötigt."
        ]
    if disk_free_gb < DISK_YELLOW_GB:
        return "yellow", [
            f"{disk_free_gb:.0f} GB freier Speicherplatz vorhanden. "
            f"Für komfortables Arbeiten werden {DISK_YELLOW_GB:.0f} GB empfohlen."
        ]
    return "green", []


def _check_blacklist(hardware: HardwareInfo) -> list[str]:
    blacklist = _load_blacklist()
    issues: list[str] = []

    if hardware.gpu_name:
        gpu_lower = hardware.gpu_name.lower()
        for substring in blacklist.get("gpu_substrings", []):
            if substring.lower() in gpu_lower:
                issues.append(
                    f"Grafikkarte '{hardware.gpu_name}' hat möglicherweise "
                    "eingeschränkte Linux-Treiberunterstützung."
                )
                break

    if hardware.wlan_chipset:
        wlan_lower = hardware.wlan_chipset.lower()
        for substring in blacklist.get("wlan_substrings", []):
            if substring.lower() in wlan_lower:
                issues.append(
                    f"WLAN-Chip '{hardware.wlan_chipset}' hat möglicherweise "
                    "eingeschränkte Linux-Treiberunterstützung."
                )
                break

    return issues


def _load_blacklist() -> dict[str, list[str]]:
    try:
        with _BLACKLIST_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        logger.warning("hardware_blacklist.json nicht lesbar, Blacklist-Prüfung übersprungen")
        return {"gpu_substrings": [], "wlan_substrings": []}


def _get_boot_key_hint(manufacturer: str | None) -> str | None:
    if not manufacturer:
        return None
    name_lower = manufacturer.lower()
    for fragment, key in _BOOT_KEY_MAP.items():
        if fragment in name_lower:
            return key
    return None
