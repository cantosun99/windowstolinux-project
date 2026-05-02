"""Demo-Skript: erzeugt einen Beispiel-Bericht mit fiktiven Daten.

Nutzt keine Windows-APIs (kein WMI, kein winreg).
Startet mit: python demo.py [--pdf]
"""

from __future__ import annotations

import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from windowstolinux.models import (
    AppMatch, HardwareInfo, HardwareVerdict, Report, WindowsApp,
)
from windowstolinux.output.html_renderer import render_html


def _demo_report() -> Report:
    hw = HardwareInfo(
        cpu_64bit=True,
        cpu_cores=8,
        cpu_name="Intel Core i7-12700K",
        ram_gb=16.0,
        disk_free_gb=120.0,
        gpu_name="NVIDIA GeForce RTX 3060",
        wlan_chipset="Intel Wi-Fi 6 AX200",
        manufacturer="Lenovo",
        model="ThinkPad X1 Carbon Gen 10",
    )

    verdict = HardwareVerdict(
        overall="green",
        cpu_status="green",
        ram_status="green",
        disk_status="green",
        issues=[],
        boot_key_hint="F12",
    )

    apps = [
        AppMatch(windows_app=WindowsApp(name="Mozilla Firefox 123.0.1 (x64 de)", publisher="Mozilla"),
                 category="green", linux_package="firefox", install_via="apt"),
        AppMatch(windows_app=WindowsApp(name="VLC media player 3.0.20", publisher="VideoLAN"),
                 category="green", linux_package="vlc", install_via="apt"),
        AppMatch(windows_app=WindowsApp(name="7-Zip 23.01 (x64)", publisher="Igor Pavlov"),
                 category="green", linux_package="p7zip-full", install_via="apt"),
        AppMatch(windows_app=WindowsApp(name="GIMP 2.10.36"),
                 category="green", linux_package="org.gimp.GIMP", install_via="flatpak"),
        AppMatch(windows_app=WindowsApp(name="Spotify", publisher="Spotify AB"),
                 category="green", linux_package="com.spotify.Client", install_via="flatpak"),
        AppMatch(windows_app=WindowsApp(name="OBS Studio 30.2", publisher="OBS Project"),
                 category="green", linux_package="com.obsproject.Studio", install_via="flatpak"),
        AppMatch(windows_app=WindowsApp(name="Discord", publisher="Discord Inc."),
                 category="green", linux_package="com.discordapp.Discord", install_via="flatpak"),
        AppMatch(windows_app=WindowsApp(name="Zoom 6.2.3", publisher="Zoom Video Communications"),
                 category="green", linux_package="us.zoom.Zoom", install_via="flatpak"),
        AppMatch(windows_app=WindowsApp(name="Microsoft Office Professional Plus 2019",
                                        publisher="Microsoft Corporation"),
                 category="yellow", linux_package="libreoffice", install_via="apt",
                 note="LibreOffice als vollwertige Alternative (Writer, Calc, Impress)"),
        AppMatch(windows_app=WindowsApp(name="Adobe Photoshop 2024", publisher="Adobe Inc."),
                 category="yellow", linux_package="org.gimp.GIMP", install_via="flatpak",
                 note="GIMP als Alternative, jedoch anderer Funktionsumfang"),
        AppMatch(windows_app=WindowsApp(name="Adobe Premiere Pro 2024", publisher="Adobe Inc."),
                 category="yellow", linux_package="org.kde.kdenlive", install_via="flatpak",
                 note="Kdenlive als professionelle Videobearbeitungs-Alternative"),
        AppMatch(windows_app=WindowsApp(name="Microsoft Teams (work or school)",
                                        publisher="Microsoft Corporation"),
                 category="yellow", linux_package="com.microsoft.Teams", install_via="flatpak",
                 note="Microsoft Teams ist für Linux verfügbar (Funktionsumfang eingeschränkt)"),
        AppMatch(windows_app=WindowsApp(name="AutoCAD 2024", publisher="Autodesk"),
                 category="red",
                 note="Kein Linux-Äquivalent. FreeCAD als 3D-Alternative verfügbar."),
        AppMatch(windows_app=WindowsApp(name="Microsoft Visio 2019", publisher="Microsoft"),
                 category="red",
                 note="Kein Linux-Äquivalent. draw.io (online) oder LibreOffice Draw als Alternative."),
    ]

    return Report(
        hardware=hw,
        hardware_verdict=verdict,
        apps=apps,
        generated_at=datetime.now(),
    )


def main() -> None:
    report = _demo_report()
    html   = render_html(report)

    html_path = Path("demo_report.html")
    html_path.write_text(html, encoding="utf-8")
    print(f"HTML gespeichert: {html_path.resolve()}")

    if "--pdf" in sys.argv:
        try:
            from windowstolinux.output.pdf_exporter import export_pdf
            pdf_path = Path("demo_report.pdf")
            export_pdf(html, pdf_path)
            print(f"PDF  gespeichert: {pdf_path.resolve()}")
        except Exception as exc:
            print(f"PDF-Export fehlgeschlagen: {exc}")
            print("Tipp: sudo pacman -S python-weasyprint  (oder pip install weasyprint)")

    webbrowser.open(html_path.resolve().as_uri())
    print(f"\nInstallationsbefehl im Bericht:\n{report.install_command}")


if __name__ == "__main__":
    main()
