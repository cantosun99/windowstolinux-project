# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for WindowsToLinux (Single-File Windows EXE).

Prerequisites (must be done on a Windows machine):
  -------------------------------------------------------
  1. GTK 3 runtime via MSYS2  (https://www.msys2.org)
     In an MSYS2 MinGW-w64 shell:
       pacman -S mingw-w64-x86_64-gtk3
     Then permanently add the MSYS2 bin dir to the Windows PATH:
       C:\\msys64\\mingw64\\bin
     WeasyPrint needs Cairo, Pango and GLib DLLs from this directory.

  2. Python dependencies:
       pip install -e ".[dev]"
       pip install pyinstaller>=6.0

  3. Build:
       python -m PyInstaller windowstolinux.spec --clean --noconfirm
     Or simply run:
       build.bat

Output
  dist\\WindowsToLinux.exe   (~80 MB, self-contained, no installer needed)

Windows Defender / SmartScreen note
  Unsigned PyInstaller EXEs commonly trigger a SmartScreen warning on first
  run. This is a false positive. Users can click "More info -> Run anyway"
  or, for distribution, the EXE should be code-signed.
"""

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ---------------------------------------------------------------------------
# GTK3 native DLLs (zur Laufzeit von WeasyPrint geladen)
# ---------------------------------------------------------------------------
GTK_BIN = Path(os.environ.get("GTK_BIN", r"C:\msys64\mingw64\bin"))

_GTK_DLL_PATTERNS = [
    "libgobject-2.0-",
    "libglib-2.0-",
    "libgio-2.0-",
    "libgmodule-2.0-",
    "libcairo-",
    "libcairo-gobject-",
    "libpango-1.0-",
    "libpangocairo-1.0-",
    "libpangoft2-1.0-",
    "libpangowin32-1.0-",
    "libfontconfig-",
    "libfreetype-",
    "libharfbuzz-",
    "libpixman-1-",
    "libpng16-",
    "libffi-",
    "libintl-",
    "libiconv-",
    "libwinpthread-",
    "libgcc_s_seh-",
    "libstdc++-",
    "libgdk_pixbuf-2.0-",
    "libexpat-",
    "zlib1.dll",
    "libxml2-",
    "libfribidi-",
    "libthai-",
    "libdatrie-",
    "libbz2-",
    "libgraphite2.dll",
]

_gtk_binaries: list[tuple[str, str]] = []
if GTK_BIN.is_dir():
    for dll in GTK_BIN.glob("*.dll"):
        if any(pat in dll.name for pat in _GTK_DLL_PATTERNS):
            _gtk_binaries.append((str(dll), "."))
    if not _gtk_binaries:
        raise RuntimeError(
            f"Keine GTK3-DLLs in {GTK_BIN} gefunden. "
            "Vorher: pacman -S mingw-w64-x86_64-gtk3 mingw-w64-x86_64-pango"
        )
else:
    raise RuntimeError(
        f"GTK3-Verzeichnis fehlt: {GTK_BIN}. "
        "MSYS2 installieren und: pacman -S mingw-w64-x86_64-gtk3 mingw-w64-x86_64-pango"
    )

# ---------------------------------------------------------------------------
# Collect non-Python assets from packages that carry them
# ---------------------------------------------------------------------------

_extra_datas: list[tuple[str, str]] = []
_extra_datas += collect_data_files("customtkinter")   # themes, images
_extra_datas += collect_data_files("weasyprint")      # CSS, fonts config
_extra_datas += collect_data_files("certifi")         # CA bundle for httpx
_extra_datas += collect_data_files("pyphen")
_extra_datas += collect_data_files("tinycss2")
_extra_datas += collect_data_files("cssselect2")

a = Analysis(
    ["windowstolinux/__main__.py"],
    pathex=[],
    binaries=_gtk_binaries,
    datas=[
        # Application data files
        ("windowstolinux/data",             "windowstolinux/data"),
        ("windowstolinux/output/templates", "windowstolinux/output/templates"),
        # Package assets
        *_extra_datas,
    ],
    hiddenimports=[
        # --- pydantic v2 ------------------------------------------------
        "pydantic",
        "pydantic.v1",
        "pydantic_core",
        "pydantic_core.core_schema",
        # --- Windows-only stdlib (available only when built on Windows) ---
        "winreg",
        "wmi",
        # --- HTTP client stack ------------------------------------------
        "httpx",
        "httpcore",
        "httpcore._async",
        "httpcore._sync",
        "anyio",
        "anyio.abc",
        "anyio._core",
        "certifi",
        "idna",
        # --- WeasyPrint internals ----------------------------------------
        "weasyprint",
        "weasyprint.css",
        "weasyprint.css.media_queries",
        "weasyprint.css.utils",
        "weasyprint.document",
        "weasyprint.draw",
        "weasyprint.draw.border",
        "weasyprint.draw.text",
        "weasyprint.fonts",
        "weasyprint.html",
        "weasyprint.images",
        "weasyprint.layout",
        "weasyprint.layout.block",
        "weasyprint.layout.flex",
        "weasyprint.layout.float",
        "weasyprint.layout.inline",
        "weasyprint.layout.table",
        "weasyprint.urls",
        # --- WeasyPrint dependencies ------------------------------------
        "cairocffi",
        "cairocffi.constants",
        "tinycss2",
        "tinycss2.ast",
        "cssselect2",
        "html5lib",
        "html5lib.treebuilders",
        "html5lib.treebuilders._base",
        "html5lib.treebuilders.etree",
        "fonttools",
        "fonttools.ttLib",
        "fonttools.varLib",
        "Pyphen",
        # --- Jinja2 -----------------------------------------------------
        "jinja2",
        "jinja2.ext",
        "jinja2.compiler",
        # --- CustomTkinter + all sub-packages ---------------------------
        "customtkinter",
        *collect_submodules("customtkinter"),
        # --- PIL (Pillow, required by customtkinter) --------------------
        "PIL",
        "PIL.Image",
        "PIL.ImageTk",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["runtime_hook_gtk.py"],
    excludes=[
        # Heavy scientific / data stacks not used by this app
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        # Dev / test tooling
        "pytest",
        "pytest_mock",
        "IPython",
        "jupyter",
        "tkinter.test",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="WindowsToLinux",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX compression is disabled: it meaningfully increases the
    # Defender false-positive rate without a significant size benefit.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,              # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="windowstolinux/data/windowstolinux.ico",
)
