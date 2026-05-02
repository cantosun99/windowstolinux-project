"""Flathub-API-v2-Client.

Sucht auf https://flathub.org/api/v2/search/<query> und gibt die
beste passende Flatpak-App-ID zurück. Nutzt den gemeinsamen SQLite-Cache.

Cache-Sentinel: Leerer String = "gesucht, kein Ergebnis gefunden".
"""

from __future__ import annotations

import logging

import httpx

from windowstolinux.resolver import cache

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://flathub.org/api/v2/search"
_TIMEOUT    = 10.0
_USER_AGENT = "WindowsToLinux/0.1 (migration report tool; contact via GitHub)"


def search(query: str) -> str | None:
    """Gibt eine Flathub-App-ID zurück, die zur Suchanfrage passt, oder None.

    Prüft zuerst den Cache. Bei Miss wird die Flathub-Such-API abgefragt
    und die App-ID des ersten Treffers zurückgegeben.
    Bei Netzwerkfehler wird ein abgelaufener Cache-Eintrag genutzt.
    """
    key = query.lower().strip()
    cache_key = f"flathub:{key}"

    cached = cache.get(cache_key)
    if cached is not None:
        return cached or None  # Leerer String-Sentinel → None

    try:
        response = httpx.get(
            f"{_SEARCH_URL}/{key}",
            timeout=_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning(f"Flathub-Anfrage für '{key}' fehlgeschlagen: {exc}")
        stale = cache.get(cache_key, allow_stale=True)
        return stale or None

    try:
        data: dict = response.json()
    except Exception:
        logger.warning(f"Flathub: kein JSON für '{key}'")
        cache.set(cache_key, "")
        return None

    app_id = _extract_app_id(data)
    cache.set(cache_key, app_id or "")
    return app_id


def _extract_app_id(data: dict) -> str | None:
    apps = data.get("apps", [])
    if apps and isinstance(apps, list):
        return apps[0].get("id") or None
    return None
