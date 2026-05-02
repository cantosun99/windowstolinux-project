"""Repology-API-v1-Client.

Fragt https://repology.org/api/v1/project/<name> ab und filtert
Ergebnisse auf Ubuntu 24.04/24.10 und Linux-Mint-Repositories.
Nutzt den SQLite-Cache mit 7-Tage-TTL.

Cache-Sentinel: Leerer String = "abgefragt, nicht in relevanten Repos gefunden".
Rate-Limit:     Maximal eine HTTP-Anfrage pro Sekunde (Cache-Treffer sind kostenlos).
"""

from __future__ import annotations

import logging
import time

import httpx

from windowstolinux.resolver import cache

logger = logging.getLogger(__name__)

RELEVANT_REPOS = frozenset({"ubuntu_24_04", "ubuntu_24_10", "linuxmint"})

_BASE_URL            = "https://repology.org/api/v1/project"
_TIMEOUT             = 10.0
_USER_AGENT          = "WindowsToLinux/0.1 (migration report tool; contact via GitHub)"
_MIN_REQUEST_INTERVAL = 1.0  # Sekunden zwischen echten HTTP-Anfragen

_last_request_at: float = 0.0


def lookup(package_name: str) -> str | None:
    """Gibt den apt-Binärnamen zurück, wenn das Paket in einem relevanten Repo existiert.

    Prüft zuerst den Cache. Bei Miss wird die Repology-API abgefragt
    (rate-limitiert auf eine Anfrage/Sekunde). Bei Netzwerkfehler wird
    ein abgelaufener Cache-Eintrag als Fallback genutzt.
    """
    name = package_name.lower().strip()
    cache_key = f"repology:{name}"

    cached = cache.get(cache_key)
    if cached is not None:
        return cached or None  # Leerer String-Sentinel → None

    _throttle()

    try:
        response = httpx.get(
            f"{_BASE_URL}/{name}",
            timeout=_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning(f"Repology-Anfrage für '{name}' fehlgeschlagen: {exc}")
        stale = cache.get(cache_key, allow_stale=True)
        return stale or None

    try:
        data: list[dict] = response.json()
    except Exception:
        # Repology liefert bei mehrdeutigen Namen eine HTML-Seite statt JSON.
        logger.debug(f"Repology: kein JSON für '{name}' (Disambiguierungs-Seite)")
        cache.set(cache_key, "")
        return None

    bin_name = _extract_bin_name(data)
    cache.set(cache_key, bin_name or "")
    return bin_name


def _throttle() -> None:
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_at = time.monotonic()


def _extract_bin_name(data: list[dict]) -> str | None:
    for entry in data:
        if entry.get("repo") in RELEVANT_REPOS:
            bin_name = entry.get("binname", "")
            if bin_name:
                return bin_name
    return None
