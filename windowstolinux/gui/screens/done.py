"""Abschluss-Screen: bestätigt den PDF-Export und zeigt den Speicherpfad."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import customtkinter as ctk

_BG_HEADER = "#166534"
_FG_HEADER = "#ffffff"


class DoneScreen(ctk.CTkFrame):
    """Wird nach erfolgreichem PDF-Export angezeigt."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        pdf_path: Path,
        on_restart: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color="#ffffff")
        self._pdf_path   = pdf_path
        self._on_restart = on_restart
        self._build()

    def _build(self) -> None:
        # Grüner Header signalisiert Erfolg
        header = ctk.CTkFrame(self, fg_color=_BG_HEADER, corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(
            header,
            text="PDF erfolgreich gespeichert",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=_FG_HEADER,
        ).pack(pady=(22, 20))

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=60, pady=40)

        ctk.CTkLabel(
            content,
            text="Ihr Migrationsbericht wurde gespeichert unter:",
            font=ctk.CTkFont(size=13),
            text_color="#374151",
        ).pack(pady=(0, 8))

        path_box = ctk.CTkFrame(content, fg_color="#f1f5f9", corner_radius=6)
        path_box.pack(fill="x", pady=(0, 28))

        ctk.CTkLabel(
            path_box,
            text=str(self._pdf_path),
            font=ctk.CTkFont(size=11, family="Courier"),
            text_color="#1e3a5f",
            wraplength=520,
        ).pack(padx=14, pady=10)

        ctk.CTkLabel(
            content,
            text=(
                "Öffnen Sie den Bericht und lesen Sie die Hinweise\n"
                "sorgfältig durch, bevor Sie Linux Mint installieren."
            ),
            font=ctk.CTkFont(size=13),
            text_color="#374151",
            justify="center",
        ).pack(pady=(0, 28))

        btn_row = ctk.CTkFrame(content, fg_color="transparent")
        btn_row.pack()

        ctk.CTkButton(
            btn_row,
            text="Datei öffnen",
            font=ctk.CTkFont(size=13),
            height=42,
            width=160,
            fg_color="#e5e7eb",
            text_color="#374151",
            hover_color="#d1d5db",
            command=self._open_file,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row,
            text="Neue Analyse starten",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=42,
            width=200,
            command=self._on_restart,
        ).pack(side="left")

    def _open_file(self) -> None:
        try:
            if sys.platform == "win32":
                import os  # noqa: PLC0415
                os.startfile(str(self._pdf_path))
            else:
                import subprocess  # noqa: PLC0415
                subprocess.Popen(["xdg-open", str(self._pdf_path)])
        except Exception:
            pass  # Fehler still ignorieren, falls kein Viewer vorhanden
