"""Scan-Screen: Fortschrittsanzeige während der Hintergrund-Analyse."""

from __future__ import annotations

import logging
import threading
from typing import Callable

import customtkinter as ctk

from windowstolinux.gui.app import run_scan
from windowstolinux.models import Report

logger = logging.getLogger(__name__)

_BG_HEADER = "#1e3a5f"
_FG_HEADER = "#ffffff"


class ScanScreen(ctk.CTkFrame):
    """Zeigt Fortschrittsbalken und Statustext während des Scans.

    Der Scan startet sofort beim Erstellen des Screens in einem Daemon-Thread.
    Der GUI-Thread wird nie blockiert; Updates laufen über after().
    """

    def __init__(
        self,
        master: ctk.CTkFrame,
        on_done: Callable[[Report], None],
        on_error: Callable[[str], None],
    ) -> None:
        super().__init__(master, fg_color="#ffffff")
        self._on_done = on_done
        self._on_error = on_error
        self._status_label: ctk.CTkLabel
        self._build()
        self._start_scan()

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color=_BG_HEADER, corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(
            header,
            text="Analyse läuft...",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=_FG_HEADER,
        ).pack(pady=(22, 20))

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=60, pady=50)

        self._status_label = ctk.CTkLabel(
            content,
            text="Vorbereitung...",
            font=ctk.CTkFont(size=13),
            text_color="#374151",
        )
        self._status_label.pack(pady=(0, 20))

        progress = ctk.CTkProgressBar(content, width=400, mode="indeterminate")
        progress.pack()
        progress.start()

        ctk.CTkLabel(
            content,
            text="Dies kann je nach Anzahl der installierten Programme einige Sekunden dauern.",
            font=ctk.CTkFont(size=11),
            text_color="#9ca3af",
        ).pack(pady=(24, 0))

    def _start_scan(self) -> None:
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self) -> None:
        try:
            report = run_scan(on_status=self._schedule_status)
            self._safe_after(lambda: self._on_done(report))
        except Exception as exc:
            logger.exception("Scan fehlgeschlagen")
            self._safe_after(lambda: self._on_error(str(exc)))

    def _schedule_status(self, text: str) -> None:
        self._safe_after(lambda: self._status_label.configure(text=text))

    def _safe_after(self, callback: Callable[[], None]) -> None:
        """Führt callback im GUI-Thread aus, sofern das Widget noch existiert."""
        try:
            if self.winfo_exists():
                self.after(0, callback)
        except Exception:
            pass  # Widget wurde bereits zerstört
