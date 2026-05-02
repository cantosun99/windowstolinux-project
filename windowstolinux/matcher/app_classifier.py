"""Windows-Programme in grün / gelb / rot klassifizieren.

Klassifikations-Reihenfolge (erste Übereinstimmung gewinnt):
  1. Statisches Mapping (windows_to_linux_mapping.json), schnellst und zuverlässigst
  2. Repology-API, prüft apt-Verfügbarkeit in Ubuntu/Mint-Repos
  3. Flathub-API, prüft Flatpak-Verfügbarkeit
  4. Open-Source-Alternativen-Liste, schlägt Ersatz vor (gelb)
  5. Kein Treffer, rot (Windows-only oder nur über Wine)
"""

from __future__ import annotations

import logging
import re

from pydantic import ValidationError

from windowstolinux.models import AppMatch, WindowsApp
from windowstolinux.normalizer import find_in_mapping, normalize_app_name
from windowstolinux.resolver import flathub, mappings, repology

logger = logging.getLogger(__name__)


def classify_all(apps: list[WindowsApp]) -> list[AppMatch]:
    """Klassifiziert eine Liste von Apps; lädt statische Daten nur einmal."""
    mapping      = mappings.load_windows_to_linux()
    alternatives = mappings.load_opensource_alternatives()
    return [_classify_one(app, mapping, alternatives) for app in apps]


def classify_app(app: WindowsApp) -> AppMatch:
    """Klassifiziert eine einzelne App. Für Stapelverarbeitung classify_all bevorzugen."""
    return classify_all([app])[0]


def _classify_one(
    app: WindowsApp,
    mapping: dict[str, dict],
    alternatives: dict[str, dict],
) -> AppMatch:
    norm = normalize_app_name(app.name)
    return (
        _from_static_mapping(app, norm, mapping)
        or _from_repology(app, norm)
        or _from_flathub(app, norm)
        or _from_alternatives(app, norm, alternatives)
        or _red_verdict(app)
    )


def _from_static_mapping(
    app: WindowsApp, name: str, mapping: dict[str, dict]
) -> AppMatch | None:
    entry = find_in_mapping(name, mapping)
    if not entry:
        return None
    logger.debug(f"Statisches Mapping gefunden für '{app.name}'")
    try:
        return AppMatch(
            windows_app=app,
            category=entry["category"],
            linux_package=entry.get("linux_package") or None,
            install_via=entry.get("install_via") or None,
            note=entry.get("note") or None,
        )
    except (KeyError, ValidationError) as exc:
        logger.warning(f"Ungültiger Mapping-Eintrag für '{app.name}', übersprungen: {exc}")
        return None


def _from_repology(app: WindowsApp, name: str) -> AppMatch | None:
    bin_name = repology.lookup(name)
    if not bin_name:
        return None
    logger.debug(f"Repology-Treffer für '{app.name}': {bin_name}")
    return AppMatch(
        windows_app=app,
        category="green",
        linux_package=bin_name,
        install_via="apt",
    )


def _from_flathub(app: WindowsApp, name: str) -> AppMatch | None:
    """Sucht auf Flathub; gibt grünes AppMatch mit Flatpak-ID zurück oder None.

    Plausibilitätsprüfung verhindert Fehlzuordnungen wie GIMP für Photoshop.
    """
    app_id = flathub.search(name)
    if not app_id:
        return None
    if not _flathub_id_plausible(name, app_id):
        logger.debug(f"Flathub-Ergebnis '{app_id}' für '{app.name}' als unplausibel abgelehnt")
        return None
    logger.debug(f"Flathub-Treffer für '{app.name}': {app_id}")
    return AppMatch(
        windows_app=app,
        category="green",
        linux_package=app_id,
        install_via="flatpak",
    )


def _from_alternatives(
    app: WindowsApp, name: str, alternatives: dict[str, dict]
) -> AppMatch | None:
    entry = find_in_mapping(name, alternatives)
    if not entry:
        return None
    logger.debug(f"Alternative gefunden für '{app.name}': {entry.get('alternative')}")
    try:
        return AppMatch(
            windows_app=app,
            category="yellow",
            linux_package=entry.get("linux_package") or None,
            install_via=entry.get("install_via") or None,
            note=entry.get("note") or f"Alternative verfügbar: {entry['alternative']}",
        )
    except (KeyError, ValidationError) as exc:
        logger.warning(f"Ungültiger Alternativen-Eintrag für '{app.name}', übersprungen: {exc}")
        return None


def _red_verdict(app: WindowsApp) -> AppMatch:
    logger.debug(f"Kein Linux-Äquivalent für '{app.name}'")
    return AppMatch(
        windows_app=app,
        category="red",
        note="Kein Linux-Äquivalent gefunden. Unter Wine möglicherweise ausführbar.",
    )


def _flathub_id_plausible(query: str, app_id: str) -> bool:
    """Gibt True zurück, wenn die Flathub-ID plausibel zur Suchanfrage passt.

    Prüft, ob ein signifikantes Wort (>= 2 Zeichen) aus der Anfrage in der
    App-ID vorkommt. Verhindert z. B., dass GIMP für "Adobe Photoshop" akzeptiert wird.
    """
    words = [w for w in re.split(r"[\W_]+", query) if len(w) >= 2]
    id_lower = app_id.lower()
    return any(word in id_lower for word in words)
