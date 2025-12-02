from util import *
from emulator import Emulator
from test import *
import shutil


class BDM(Emulator):
    CORNER_TIMEOUT = 15.0

    def __init__(self):
        super().__init__("Beaten Dying Moon", "https://mattcurrie.com/bdm-demo/", startup_time=5.0, features=(PCM,))
        self.title_check = lambda title: "Beaten Dying Moon" in title

    def setup(self):
        download("https://mattcurrie.com/bdm/downloads/bdms-win.zip", "downloads/bdm.zip")
        extract("downloads/bdm.zip", "emu/bdm")
        setDPIScaling("emu/bdm/bdms.exe")
        download("https://gbdev.gg8.se/files/roms/bootroms/cgb_boot.bin", "emu/bdm/cgb_boot.bin")
        download("https://gbdev.gg8.se/files/roms/bootroms/dmg_boot.bin", "emu/bdm/dmg_boot.bin")
        download("https://gbdev.gg8.se/files/roms/bootroms/sgb_boot.bin", "emu/bdm/sgb_boot.bin")
    
    def startProcess(self, rom, *, model, required_features):
        model = {DMG: "dmgC", CGB: "cgbE", SGB: "sgb"}.get(model)
        if model is None:
            return None
        process = subprocess.Popen(["emu/bdm/bdms.exe", "-scale", "1", "-turbo", "-dev", model, os.path.abspath(rom)], cwd="emu/bdm")
        forceSquareCornersAsync(self.title_check, timeout=self.CORNER_TIMEOUT)
        return process
