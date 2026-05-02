"""Einstiegspunkt: richtet Datei-Logging ein und startet die GUI.

Ungefangene Exceptions werden ins Log geschrieben und dem Nutzer
als verständlicher Dialog angezeigt statt lautlos zu verschwinden.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path


def _get_log_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    log_dir = Path(base) / "WindowsToLinux"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "app.log"


def _setup_logging() -> None:
    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.handlers.RotatingFileHandler(
        _get_log_path(),
        maxBytes=2 * 1024 * 1024,  # 2 MB pro Datei
        backupCount=2,
        encoding="utf-8",
    )
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)

    logging.getLogger(__name__).info(
        "WindowsToLinux gestartet (Python %s)", sys.version.split()[0]
    )


def _show_crash_dialog(exc: BaseException) -> None:
    try:
        from tkinter import messagebox  # noqa: PLC0415
        messagebox.showerror(
            "Unerwarteter Fehler",
            "WindowsToLinux ist auf einen unerwarteten Fehler gestoßen "
            "und muss beendet werden.\n\n"
            f"Fehlertyp: {type(exc).__name__}\n"
            f"Details:   {exc}\n\n"
            "Die vollständige Fehlermeldung wurde in der Logdatei gespeichert:\n"
            f"{_get_log_path()}",
        )
    except Exception:  # noqa: BLE001 - tkinter könnte selbst defekt sein
        pass


def main() -> None:
    _setup_logging()
    logger = logging.getLogger(__name__)

    try:
        from windowstolinux.gui.app import App  # noqa: PLC0415

        app = App()
        app.mainloop()
        logger.info("Anwendung normal beendet")
    except Exception as exc:
        logger.critical("Unbehandelter Fehler", exc_info=True)
        _show_crash_dialog(exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
