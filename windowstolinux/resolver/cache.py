"""SQLite-Cache für alle Resolver-Clients.

Speichert API-Antworten lokal, um wiederholte Netzwerkanfragen zu vermeiden.

Datei:   %LOCALAPPDATA%\\WindowsToLinux\\cache.db (Windows-Standard).
Überschreiben: Umgebungsvariable WINDOWSTOLINUX_CACHE_PATH setzen
               (nützlich für Tests und Nicht-Windows-Umgebungen).

TTL:      7 Tage. Bei Cache-Miss holt der Aufrufer frische Daten.
Stale:    Bei Netzwerkfehler kann allow_stale=True übergeben werden,
          um einen abgelaufenen Eintrag als Fallback zu nutzen.
Sentinel: Ein leerer String bedeutet "nachgeschlagen, nicht gefunden".
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_TTL_SECONDS = 7 * 24 * 3600  # 7 Tage

_CREATE_TABLE = (
    "CREATE TABLE IF NOT EXISTS cache "
    "(key TEXT PRIMARY KEY, value TEXT NOT NULL, cached_at REAL NOT NULL)"
)


def get_cache_path() -> Path:
    """Gibt den Pfad zur SQLite-Cache-Datei zurück.

    Liest zuerst WINDOWSTOLINUX_CACHE_PATH, dann %LOCALAPPDATA%.
    """
    if env := os.environ.get("WINDOWSTOLINUX_CACHE_PATH"):
        return Path(env)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "WindowsToLinux" / "cache.db"


def get(key: str, *, allow_stale: bool = False) -> str | None:
    """Gibt den gecachten Wert für key zurück, oder None bei Miss / Ablauf.

    allow_stale=True liefert auch abgelaufene Einträge (Netzwerk-Fallback).
    Ein leerer String bedeutet: Lookup war erfolgreich, Ergebnis war "nicht gefunden".
    """
    conn = None
    try:
        conn = _open()
        cutoff = 0.0 if allow_stale else time.time() - _TTL_SECONDS
        row = conn.execute(
            "SELECT value FROM cache WHERE key = ? AND cached_at >= ?",
            (key, cutoff),
        ).fetchone()
        return row[0] if row else None
    except sqlite3.Error as exc:
        logger.warning(f"Cache-Lesefehler für '{key}': {exc}")
        return None
    finally:
        if conn:
            conn.close()


def set(key: str, value: str) -> None:
    """Speichert einen Wert unter key mit aktuellem Zeitstempel.

    Leeren String verwenden, um ein "nicht gefunden"-Ergebnis zu cachen.
    """
    conn = None
    try:
        conn = _open()
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, cached_at) VALUES (?, ?, ?)",
            (key, value, time.time()),
        )
        conn.commit()
    except sqlite3.Error as exc:
        logger.warning(f"Cache-Schreibfehler für '{key}': {exc}")
    finally:
        if conn:
            conn.close()


def _open() -> sqlite3.Connection:
    """Öffnet (oder erstellt) die Cache-DB und stellt das Schema sicher."""
    path = get_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(_CREATE_TABLE)
    return conn
