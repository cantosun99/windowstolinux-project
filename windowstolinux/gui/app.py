"""Hauptfenster und Scan-Pipeline-Orchestrierung.

run_scan() und export_report() enthalten die gesamte Geschäftslogik
ohne CTk-Abhängigkeit und sind daher ohne Display testbar.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

import sys

import customtkinter as ctk

from windowstolinux.matcher.app_classifier import classify_all
from windowstolinux.matcher.hardware_check import check_hardware
from windowstolinux.models import Report
from windowstolinux.output.html_renderer import render_html
from windowstolinux.output.pdf_exporter import export_pdf
from windowstolinux.scanner.apps import scan_installed_apps
from windowstolinux.scanner.hardware import scan_hardware

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# Geschäftslogik (ohne CTk-Abhängigkeit, vollständig testbar)


def run_scan(on_status: Callable[[str], None]) -> Report:
    """Führt die vollständige Hardware- und App-Scan-Pipeline aus.

    Gedacht für Ausführung in einem Hintergrund-Thread. Ruft on_status vor
    jedem Schritt auf, damit die GUI den Fortschritt anzeigen kann.
    on_status muss thread-sicher sein (bei CTk mit after() wrappen).
    """
    on_status("Hardware wird analysiert...")
    hw = scan_hardware()

    on_status("Hardware wird bewertet...")
    verdict = check_hardware(hw)

    on_status("Installierte Programme werden erkannt...")
    apps = scan_installed_apps()

    on_status(f"{len(apps)} Programme gefunden, werden klassifiziert...")
    matches = classify_all(apps)

    return Report(hardware=hw, hardware_verdict=verdict, apps=matches)


def export_report(report: Report, output_path: Path) -> None:
    """Rendert den Bericht als HTML und speichert ihn als PDF."""
    html = render_html(report)
    export_pdf(html, output_path)


class App(ctk.CTk):
    """Hauptfenster; verwaltet den Screen-Stack und steuert die Übergänge."""

    def __init__(self) -> None:
        super().__init__()
        self.title("WindowsToLinux")
        self.geometry("700x520")
        self.resizable(False, False)
        _base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
        _icon = _base / "windowstolinux" / "data" / "windowstolinux.ico"
        if _icon.exists():
            self.iconbitmap(str(_icon))
        self._report: Report | None = None
        self._container = ctk.CTkFrame(self, fg_color="transparent")
        self._container.pack(fill="both", expand=True)
        self._current: ctk.CTkFrame | None = None
        self._show_start()

    def _show_start(self) -> None:
        from windowstolinux.gui.screens.start import StartScreen  # noqa: PLC0415
        self._switch(StartScreen(self._container, on_start=self._show_scan))

    def _show_scan(self) -> None:
        from windowstolinux.gui.screens.scan import ScanScreen  # noqa: PLC0415
        self._switch(ScanScreen(
            self._container,
            on_done=self._show_result,
            on_error=self._show_error,
        ))

    def _show_result(self, report: Report) -> None:
        from windowstolinux.gui.screens.result import ResultScreen  # noqa: PLC0415
        self._report = report
        self._switch(ResultScreen(
            self._container,
            report=report,
            on_export=self._do_export,
            on_restart=self._show_start,
        ))

    def _show_done(self, pdf_path: Path) -> None:
        from windowstolinux.gui.screens.done import DoneScreen  # noqa: PLC0415
        self._switch(DoneScreen(
            self._container,
            pdf_path=pdf_path,
            on_restart=self._show_start,
        ))

    def _show_error(self, message: str) -> None:
        from tkinter import messagebox  # noqa: PLC0415
        messagebox.showerror(
            "Fehler bei der Analyse",
            f"Die Analyse konnte nicht abgeschlossen werden:\n\n{message}",
        )
        self._show_start()

    def _do_export(self) -> None:
        if self._report is None:
            return
        from tkinter import filedialog  # noqa: PLC0415
        path_str = filedialog.asksaveasfilename(
            title="PDF speichern unter",
            defaultextension=".pdf",
            filetypes=[("PDF-Datei", "*.pdf"), ("Alle Dateien", "*.*")],
            initialfile="Linux-Migrationsbericht.pdf",
        )
        if not path_str:
            return
        try:
            export_report(self._report, Path(path_str))
            self._show_done(Path(path_str))
        except Exception as exc:
            logger.error(f"PDF-Export fehlgeschlagen: {exc}")
            from tkinter import messagebox  # noqa: PLC0415
            messagebox.showerror(
                "Export fehlgeschlagen",
                f"Das PDF konnte nicht gespeichert werden:\n\n{exc}",
            )

    def _switch(self, screen: ctk.CTkFrame) -> None:
        if self._current is not None:
            self._current.destroy()
        self._current = screen
        screen.pack(fill="both", expand=True)
