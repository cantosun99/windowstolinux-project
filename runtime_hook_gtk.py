import os
import sys

if hasattr(sys, "_MEIPASS"):
    bundle_dir = sys._MEIPASS
    os.environ["PATH"] = bundle_dir + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(bundle_dir)
        except (OSError, FileNotFoundError):
            pass
