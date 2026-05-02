"""HTML-String mit WeasyPrint als PDF-Datei speichern."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def export_pdf(html: str, output_path: Path) -> None:
    """Schreibt den HTML-Bericht als PDF an den angegebenen Pfad.

    WeasyPrint benötigt unter Windows GTK-Bibliotheken. Beim PyInstaller-Build
    müssen diese mitgepackt werden (siehe WeasyPrint-Dokumentation).
    Wirft alle WeasyPrint-Fehler nach dem Logging weiter.
    """
    import weasyprint  # noqa: PLC0415 (schwerer Import, bewusst verzögert)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        weasyprint.HTML(string=html).write_pdf(str(output_path))
        logger.info(f"PDF gespeichert: '{output_path}'")
    except Exception as exc:
        logger.error(f"PDF-Export fehlgeschlagen: {exc}")
        raise
