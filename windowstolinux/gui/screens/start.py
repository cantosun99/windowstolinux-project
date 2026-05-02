"""Willkommens-Screen mit dem 'Analyse starten'-Button."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

_BG_HEADER = "#1e3a5f"
_FG_HEADER = "#ffffff"


class StartScreen(ctk.CTkFrame):
    """Erster Screen nach dem Start; Nutzer löst hier den Scan aus."""

    def __init__(self, master: ctk.CTkFrame, on_start: Callable[[], None]) -> None:
        super().__init__(master, fg_color="#ffffff")
        self._on_start = on_start
        self._build()

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color=_BG_HEADER, corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(
            header,
            text="WindowsToLinux",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=_FG_HEADER,
        ).pack(pady=(22, 2))

        ctk.CTkLabel(
            header,
            text="Ihr persönlicher Umstiegs-Assistent",
            font=ctk.CTkFont(size=12),
            text_color="#93c5fd",
        ).pack(pady=(0, 20))

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=60, pady=40)

        ctk.CTkLabel(
            content,
            text="Bereit für Linux Mint?",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#111827",
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            content,
            text=(
                "Diese App analysiert Ihren Computer und erstellt einen persönlichen\n"
                "Bericht, welche Ihrer Programme unter Linux Mint verfügbar sind\n"
                "und wie gut Ihre Hardware unterstützt wird."
            ),
            font=ctk.CTkFont(size=13),
            text_color="#374151",
            justify="center",
        ).pack(pady=(0, 32))

        ctk.CTkButton(
            content,
            text="Analyse starten",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=46,
            width=220,
            command=self._on_start,
        ).pack()

        ctk.CTkLabel(
            self,
            text="Nur für Windows 10/11 auf 64-Bit-PCs. Ziel: Linux Mint 22 Cinnamon.",
            font=ctk.CTkFont(size=10),
            text_color="#9ca3af",
        ).pack(side="bottom", pady=12)
