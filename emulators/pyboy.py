from util import *
from emulator import Emulator
from test import *
import shutil
import os
import sys


class PyBoy(Emulator):
    def __init__(self):
        super().__init__("PyBoy", "https://github.com/Baekalfen/PyBoy", startup_time=5.0)
        # PyBoy's window title has changed across versions/backends.
        # Older versions show performance stats like "CPU/frame: ... Emulation: ...".
        # Newer versions/backends may show a simpler "PyBoy" title.
        self.title_check = lambda title: (
            ("cpu/frame" in title.lower())
            or ("emulation" in title.lower())
            or ("pyboy" in title.lower())
        )

    def setup(self):
        download("https://gbdev.gg8.se/files/roms/bootroms/cgb_boot.bin", "emu/pyboy/cgb_boot.bin")
        download("https://gbdev.gg8.se/files/roms/bootroms/dmg_boot.bin", "emu/pyboy/dmg_boot.bin")
        setDPIScaling(sys.executable)
        
        subprocess.Popen([sys.executable, "-m", "pip", "install", "pysdl2-dll"], cwd="emu/pyboy").wait()
        subprocess.Popen([sys.executable, "-m", "pip", "install", "pyboy"], cwd="emu/pyboy").wait()
    
    def startProcess(self, rom, *, model, required_features):
        if model not in (DMG, CGB):
            return None

        model_flag = "--dmg" if model == DMG else "--cgb"
        bootrom = "dmg_boot.bin" if model == DMG else "cgb_boot.bin"
        # Force SDL2 window backend: the default backend can vary and OpenGL init
        # can be unreliable/slow on some CI runners.
        return subprocess.Popen(
            [
                sys.executable,
                "-m",
                "pyboy",
                "--window",
                "SDL2",
                model_flag,
                "--no-input",
                "-b",
                bootrom,
                "-s",
                "1",
                os.path.abspath(rom),
            ],
            cwd="emu/pyboy",
        )
