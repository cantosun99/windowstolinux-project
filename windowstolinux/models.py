"""Pydantic-Datenmodelle für WindowsToLinux."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field, model_validator

Status = Literal["green", "yellow", "red"]
InstallVia = Literal["apt", "flatpak"]


class HardwareInfo(BaseModel):
    """Rohe Hardware-Daten des lokalen Systems."""

    cpu_64bit: bool
    cpu_cores: int
    cpu_name: str
    ram_gb: float
    disk_free_gb: float
    gpu_name: str | None = None
    wlan_chipset: str | None = None
    manufacturer: str | None = None
    model: str | None = None


class HardwareVerdict(BaseModel):
    """Bewertungsergebnis der Hardware-Analyse."""

    overall: Status
    cpu_status: Status
    ram_status: Status
    disk_status: Status
    issues: list[str] = []
    boot_key_hint: str | None = None  # z. B. "F12" für Lenovo, "F9" für HP


class WindowsApp(BaseModel):
    """Ein Programm-Eintrag aus der Windows-Registry."""

    name: str
    publisher: str | None = None
    version: str | None = None


class AppMatch(BaseModel):
    """Klassifikationsergebnis für ein einzelnes Windows-Programm."""

    windows_app: WindowsApp
    category: Status
    linux_package: str | None = None   # apt-Paketname oder Flathub-ID
    install_via: InstallVia | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _package_and_via_consistent(self) -> AppMatch:
        """Stellt sicher, dass linux_package und install_via beide gesetzt oder beide None sind."""
        has_package = self.linux_package is not None
        has_via = self.install_via is not None
        if has_package != has_via:
            raise ValueError(
                "linux_package and install_via must both be set or both be None"
            )
        return self


class Report(BaseModel):
    """Vollständiger Migrationsbericht mit Hardware- und Programm-Analyse."""

    hardware: HardwareInfo
    hardware_verdict: HardwareVerdict
    apps: list[AppMatch]
    generated_at: datetime = Field(default_factory=datetime.now)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def green_count(self) -> int:
        return sum(1 for a in self.apps if a.category == "green")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def yellow_count(self) -> int:
        return sum(1 for a in self.apps if a.category == "yellow")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def red_count(self) -> int:
        return sum(1 for a in self.apps if a.category == "red")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def install_command(self) -> str:
        """Einzeiler-Installationsbefehl für alle verfügbaren Linux-Pakete."""
        apt_packages = sorted({
            a.linux_package
            for a in self.apps
            if a.install_via == "apt" and a.linux_package
        })
        flatpak_ids = sorted({
            a.linux_package
            for a in self.apps
            if a.install_via == "flatpak" and a.linux_package
        })

        parts: list[str] = []
        if apt_packages:
            parts.append(f"sudo apt install -y {' '.join(apt_packages)}")
        for fid in flatpak_ids:
            parts.append(f"flatpak install -y flathub {fid}")

        return " && \\\n  ".join(parts)
