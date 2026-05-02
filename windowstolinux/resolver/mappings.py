"""Statische JSON-Mapping-Dateien aus dem data-Verzeichnis laden.

Ermöglicht schnelle lokale Lookups vor externen API-Abfragen.
Alle Schlüssel der zurückgegebenen Dicts sind kleingeschrieben.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data"


def load_windows_to_linux() -> dict[str, dict]:
    """Lädt die Windows-zu-Linux-Pakettabelle aus der JSON-Datei."""
    return _load_json("windows_to_linux_mapping.json")


def load_opensource_alternatives() -> dict[str, dict]:
    """Lädt die Liste der Open-Source-Alternativen aus der JSON-Datei."""
    return _load_json("opensource_alternatives.json")


def _load_json(filename: str) -> dict[str, dict]:
    """Liest eine JSON-Mapping-Datei aus dem data-Verzeichnis.

    Entfernt den internen _comment-Schlüssel und gibt bei Fehler {} zurück.
    """
    path = _DATA_DIR / filename
    try:
        with path.open(encoding="utf-8") as f:
            data: dict = json.load(f)
        data.pop("_comment", None)
        return data
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"Konnte '{filename}' nicht laden: {exc}")
        return {}
