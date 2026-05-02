"""Hardware-Informationen des lokalen Windows-Systems auslesen.

Nutzt psutil für CPU/RAM/Disk, platform für die Architektur und WMI
für GPU, WLAN-Chip und Mainboard-Infos. Alle WMI-Abfragen werden über
eine einzige Verbindung gebündelt, um Latenz zu minimieren.
"""

from __future__ import annotations

import logging
import os
import platform
from pathlib import Path

import psutil

from windowstolinux.models import HardwareInfo

logger = logging.getLogger(__name__)


def scan_hardware() -> HardwareInfo:
    """Liest Hardware-Daten des aktuellen Rechners aus."""
    cpu_64bit = platform.machine() in {"AMD64", "x86_64"}
    cpu_cores = psutil.cpu_count(logical=False) or 1
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    disk_free_gb = round(_get_disk_free_gb(), 1)

    cpu_name, gpu_name, wlan_chipset, manufacturer, model = _query_wmi()

    return HardwareInfo(
        cpu_64bit=cpu_64bit,
        cpu_cores=cpu_cores,
        cpu_name=cpu_name,
        ram_gb=ram_gb,
        disk_free_gb=disk_free_gb,
        gpu_name=gpu_name,
        wlan_chipset=wlan_chipset,
        manufacturer=manufacturer,
        model=model,
    )


def _get_disk_free_gb() -> float:
    system_drive = Path(os.environ.get("SystemDrive", "C:") + "\\")
    return psutil.disk_usage(str(system_drive)).free / (1024 ** 3)


def _query_wmi() -> tuple[str, str | None, str | None, str | None, str | None]:
    """Fragt WMI nach CPU, GPU, WLAN-Chip, Hersteller und Modell ab.

    Öffnet eine einzige WMI-Verbindung für alle Abfragen.
    Bei nicht verfügbarem WMI wird platform.processor() als CPU-Fallback genutzt.
    Gibt (cpu_name, gpu_name, wlan_chipset, manufacturer, model) zurück.
    """
    try:
        import wmi  # noqa: PLC0415 (Windows-only, bewusst verzögert importiert)

        c = wmi.WMI()

        cpu_name = _wmi_cpu_name(c)
        gpu_name = _wmi_gpu_name(c)
        wlan_chipset = _wmi_wlan_chipset(c)
        manufacturer, model = _wmi_system_info(c)

        return cpu_name, gpu_name, wlan_chipset, manufacturer, model

    except Exception:
        logger.warning("WMI nicht verfügbar, Hardware-Details unvollständig", exc_info=True)
        fallback_cpu = platform.processor() or "Unbekannt"
        return fallback_cpu, None, None, None, None


def _wmi_cpu_name(c: object) -> str:
    for proc in c.Win32_Processor():  # type: ignore[attr-defined]
        return (proc.Name or "Unbekannt").strip()
    return "Unbekannt"


def _wmi_gpu_name(c: object) -> str | None:
    """Gibt den primären GPU-Namen zurück; überspringt den Microsoft Basic Display Adapter."""
    for gpu in c.Win32_VideoController():  # type: ignore[attr-defined]
        name = (gpu.Name or "").strip()
        if name and "Microsoft" not in name:
            return name
    return None


def _wmi_wlan_chipset(c: object) -> str | None:
    for adapter in c.Win32_NetworkAdapter():  # type: ignore[attr-defined]
        adapter_type = adapter.AdapterType or ""
        if "Wireless" in adapter_type or "802.11" in adapter_type:
            name = (adapter.Name or "").strip()
            return name or None
    return None


def _wmi_system_info(c: object) -> tuple[str | None, str | None]:
    for sys in c.Win32_ComputerSystem():  # type: ignore[attr-defined]
        manufacturer = (sys.Manufacturer or "").strip() or None
        model = (sys.Model or "").strip() or None
        return manufacturer, model
    return None, None
