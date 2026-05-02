"""App-Namen-Normalisierung für Windows-Registry-Einträge.

Registry-Namen tragen oft Versionsnummern, Architektur-Tags und
Sprachcodes, die für Mapping-Lookups irrelevant sind:

  "VLC media player 3.0.20"           → "vlc media player"
  "7-Zip 23.01 (x64)"                 → "7-zip"
  "Mozilla Firefox 123.0 (x64 de)"    → "mozilla firefox"
  "Microsoft Office Plus 2019 - de-de"→ "microsoft office plus"
  "Adobe Acrobat DC (64-bit)"         → "adobe acrobat dc"

normalize_app_name() entfernt diese Token und bewahrt dabei
natürlichsprachliche Klammerinhalte wie "(work or school)".

find_in_mapping() führt einen zweistufigen Lookup durch:
  1. Exakter Treffer auf den normalisierten Namen.
  2. Präfix-Treffer (längster Schlüssel zuerst) für Namen wie
     "microsoft office professional plus" → Schlüssel "microsoft office".
"""

from __future__ import annotations

import re

# " - de-de" oder " - en" am Stringende
_RE_LOCALE_SUFFIX = re.compile(
    r"\s+-\s+[a-z]{2}(?:-[a-z]{2})?$",
    re.IGNORECASE,
)

# Klammergruppen, die ausschließlich Architektur-, Versions- oder
# Sprachkürzel enthalten. Natürlichsprachliche Inhalte wie
# "(work or school)" werden nicht entfernt.
_ARCH   = r"(?:x86|x64|amd64|arm64|win32|win64|64[- ]?bit|32[- ]?bit)"
_LOCALE = r"(?:[a-z]{2}(?:-[a-z]{2})?)"
_VERNUM = r"(?:v?\d+\.\d+(?:\.\d+)*|20[0-3]\d)"
_TOKEN  = rf"(?:{_ARCH}|{_VERNUM}|{_LOCALE})"
_RE_PARENS = re.compile(
    rf"\(\s*{_TOKEN}(?:[\s,]+{_TOKEN})*\s*\)",
    re.IGNORECASE,
)

# Versionsnummern mit Punkt: "3.0.20", "v1.2.3", "14.29.30133"
_RE_VERSION_DOT = re.compile(r"\bv?\d+\.\d+(?:\.\d+)*\b")

# Jahreszahlen: "2019", "2022"
_RE_YEAR = re.compile(r"\b20[0-3]\d\b")

# Verbleibende große Build-Nummern (≥ 5 Stellen): "30133"
_RE_LARGE_NUM = re.compile(r"\b\d{5,}\b")

# Leere Klammern nach den obigen Bereinigungsschritten: "(  )"
_RE_EMPTY_PARENS = re.compile(r"\(\s*\)")

# Jede Folge von Leerzeichen oder Unterstrichen
_RE_WHITESPACE = re.compile(r"[_\s]+")



def normalize_app_name(name: str) -> str:
    """Gibt eine normalisierte Kleinschreibung eines Windows-Anzeigenamens zurück.

    Entfernt Versionsnummern, Architektur-Tags und Sprachcodes, sodass
    "VLC media player 3.0.20 (x64)" und "VLC media player" beide
    "vlc media player" ergeben.
    """
    n = name.lower().strip()
    n = _RE_LOCALE_SUFFIX.sub("", n)    # " - de-de"
    n = _RE_PARENS.sub(" ", n)          # "(x64)", "(64-bit de)"
    n = _RE_VERSION_DOT.sub(" ", n)     # "3.0.20"
    n = _RE_YEAR.sub(" ", n)            # "2019"
    n = _RE_LARGE_NUM.sub(" ", n)       # "44643"
    n = _RE_EMPTY_PARENS.sub(" ", n)    # "()"
    n = _RE_WHITESPACE.sub(" ", n).strip()
    return n


def find_in_mapping(normalized_name: str, mapping: dict[str, dict]) -> dict | None:
    """Sucht einen normalisierten App-Namen in einem Mapping-Dict.

    Stufe 1: Exakter Treffer (O(1) Hash-Lookup).
    Stufe 2: Präfix-Treffer auf längsten Schlüssel zuerst, wortgrenzenausgerichtet.
    Beispiel: "microsoft office professional plus" trifft Schlüssel "microsoft office".
    """
    if normalized_name in mapping:
        return mapping[normalized_name]

    for key in sorted(mapping, key=len, reverse=True):
        if (
            len(normalized_name) > len(key)
            and normalized_name.startswith(key)
            and normalized_name[len(key)] == " "
        ):
            return mapping[key]

    return None
