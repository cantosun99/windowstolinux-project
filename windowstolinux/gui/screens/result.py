"""Ergebnis-Screen: Hardware-Urteil und Programm-Zusammenfassung."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from windowstolinux.models import Report

_BG_HEADER = "#1e3a5f"
_FG_HEADER = "#ffffff"

_VERDICT_COLORS: dict[str, tuple[str, str]] = {
    "green":  ("#166534", "#dcfce7"),   # (Textfarbe, Hintergrundfarbe)
    "yellow": ("#854d0e", "#fef9c3"),
    "red":    ("#991b1b", "#fee2e2"),
}

_VERDICT_TEXT: dict[str, str] = {
    "green":  "Ihr Computer ist gut für Linux Mint geeignet.",
    "yellow": "Ihr Computer ist bedingt für Linux Mint geeignet.",
    "red":    "Ihr Computer erfüllt nicht alle Mindestanforderungen.",
}

_STAT_COLORS: dict[str, str] = {
    "green":  "#16a34a",
    "yellow": "#b45309",
    "red":    "#dc2626",
}


class ResultScreen(ctk.CTkFrame):
    """Zeigt die Scan-Ergebnisse und bietet den PDF-Export an."""

    def __init__(
        self,
        master: ctk.CTkFrame,
        report: Report,
        on_export: Callable[[], None],
        on_restart: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color="#ffffff")
        self._report    = report
        self._on_export  = on_export
        self._on_restart = on_restart
        self._build()

    def _build(self) -> None:
        v = self._report.hardware_verdict

        header = ctk.CTkFrame(self, fg_color=_BG_HEADER, corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(
            header,
            text="Analyse abgeschlossen",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=_FG_HEADER,
        ).pack(pady=(18, 18))

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=20)

        # Hardware-Urteilsbox
        txt_color, bg_color = _VERDICT_COLORS[v.overall]
        hw_box = ctk.CTkFrame(content, fg_color=bg_color, corner_radius=6)
        hw_box.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(
            hw_box,
            text="Hardware",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=txt_color,
        ).pack(anchor="w", padx=14, pady=(10, 2))

        ctk.CTkLabel(
            hw_box,
            text=_VERDICT_TEXT[v.overall],
            font=ctk.CTkFont(size=13),
            text_color=txt_color,
        ).pack(anchor="w", padx=14)

        for issue in v.issues:
            ctk.CTkLabel(
                hw_box,
                text=f"  - {issue}",
                font=ctk.CTkFont(size=11),
                text_color=txt_color,
                wraplength=580,
                justify="left",
            ).pack(anchor="w", padx=14)

        if v.boot_key_hint:
            ctk.CTkLabel(
                hw_box,
                text=f"  Boot-Taste: {v.boot_key_hint}",
                font=ctk.CTkFont(size=11),
                text_color=txt_color,
            ).pack(anchor="w", padx=14, pady=(2, 0))

        ctk.CTkFrame(hw_box, fg_color="transparent", height=8).pack()

        # Statistikleiste: grün / gelb / rot nebeneinander
        self._build_stats_bar(content)

        ctk.CTkFrame(content, fg_color="transparent", height=4).pack()

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(side="bottom", pady=20)

        ctk.CTkButton(
            btn_row,
            text="PDF-Bericht exportieren",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44,
            width=220,
            command=self._on_export,
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            btn_row,
            text="Neue Analyse",
            font=ctk.CTkFont(size=13),
            height=44,
            width=140,
            fg_color="#e5e7eb",
            text_color="#374151",
            hover_color="#d1d5db",
            command=self._on_restart,
        ).pack(side="left")

    def _build_stats_bar(self, parent: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.pack(fill="x")

        stats = [
            (self._report.green_count,  "Direkt verfügbar",    "green"),
            (self._report.yellow_count, "Alternative vorhanden", "yellow"),
            (self._report.red_count,    "Kein Äquivalent",      "red"),
        ]

        for count, label, status in stats:
            box = ctk.CTkFrame(
                bar, fg_color="#f8fafc", corner_radius=6,
                border_width=1, border_color="#e5e7eb",
            )
            box.pack(side="left", fill="both", expand=True, padx=4)

            ctk.CTkLabel(
                box,
                text=str(count),
                font=ctk.CTkFont(size=28, weight="bold"),
                text_color=_STAT_COLORS[status],
            ).pack(pady=(12, 2))

            ctk.CTkLabel(
                box,
                text=label,
                font=ctk.CTkFont(size=10),
                text_color="#6b7280",
            ).pack(pady=(0, 12))
