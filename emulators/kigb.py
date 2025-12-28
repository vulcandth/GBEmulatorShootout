from util import *
from emulator import Emulator
from test import *
import os
import shutil
import zipfile


class KiGB(Emulator):
    def __init__(self):
        super().__init__("KiGB", "http://kigb.emuunlim.com/", startup_time=1.6)

    def setup(self):
        download("http://kigb.emuunlim.com/kigb_win.zip", "downloads/kigb.zip")

        kigb_dir = os.path.join("emu", "kigb")
        exe_path = os.path.join(kigb_dir, "kigb.exe")

        # In CI/checkouts, `emu/kigb` may exist (so util.extract() no-ops) but be missing
        # the actual executable/DLLs. Ensure the required files are present.
        required = [
            "kigb.exe",
            "alleg40.dll",
            "hawknl.dll",
            "pthreadvce.dll",
            "zlib.dll",
        ]
        need_refresh = not all(os.path.exists(os.path.join(kigb_dir, f)) for f in required)
        if need_refresh:
            tmp = os.path.join("downloads", "_kigb_extract")
            if os.path.exists(tmp):
                shutil.rmtree(tmp)
            extract("downloads/kigb.zip", tmp)

            # Some zips contain a single top-level folder; normalize that away.
            inner = tmp
            try:
                entries = os.listdir(tmp)
                if len(entries) == 1 and os.path.isdir(os.path.join(tmp, entries[0])):
                    inner = os.path.join(tmp, entries[0])
            except Exception:
                inner = tmp

            os.makedirs(kigb_dir, exist_ok=True)
            for root, dirs, files in os.walk(inner):
                rel = os.path.relpath(root, inner)
                dst_root = kigb_dir if rel == "." else os.path.join(kigb_dir, rel)
                os.makedirs(dst_root, exist_ok=True)
                for d in dirs:
                    os.makedirs(os.path.join(dst_root, d), exist_ok=True)
                for name in files:
                    shutil.copy2(os.path.join(root, name), os.path.join(dst_root, name))

            shutil.rmtree(tmp)

        if os.path.exists(exe_path):
            setDPIScaling(exe_path)
    
    def startProcess(self, rom, *, model, required_features):
        model = {DMG: 0, CGB: 1, SGB: 4}.get(model)
        if model is None:
            return None
        kigb_dir = os.path.join("emu", "kigb")
        exe_path = os.path.join(kigb_dir, "kigb.exe")
        cfg_path = os.path.join(kigb_dir, "kigb.cfg")

        with open(cfg_path, "wt", encoding="utf-8", newline="\n") as f:
            f.write("""
SIZE_FACTOR = 1
EMU_TYPE = %d
PALETTE = 1
GB_DEVICE = 1
GBC_REAL_COLOR = 1
SGB_BORDER = 0
EMU_SPEED = 2
""" % (model))

        if not os.path.exists(exe_path):
            raise FileNotFoundError(f"KiGB executable not found at {exe_path}. Run KiGB.setup() successfully first.")

        return subprocess.Popen(
            [os.path.abspath(exe_path), os.path.abspath(rom)],
            cwd=os.path.abspath(kigb_dir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
