from util import *
from emulator import Emulator
from test import *
import shutil
import requests
import re


class Emulicious(Emulator):
    CORNER_TIMEOUT = 15.0

    def __init__(self):
        super().__init__("Emulicious", "https://emulicious.net/", startup_time=1.0, features=(PCM,))
    
    def setup(self):
        download("https://emulicious.net/download/emulicious/?wpdmdl=205", "downloads/Emulicious.zip")
        extract("downloads/Emulicious.zip", "emu/emulicious")
        download("https://gbdev.gg8.se/files/roms/bootroms/cgb_boot.bin", "emu/emulicious/cgb_boot.bin")
        download("https://gbdev.gg8.se/files/roms/bootroms/dmg_boot.bin", "emu/emulicious/dmg_boot.bin")

    def startProcess(self, rom, *, model, required_features):
        if model == DMG:
            shutil.copyfile(os.path.join(os.path.dirname(__file__), "emulicious.dmg.ini"), "emu/emulicious/Emulicious.ini")
        elif model == CGB:
            shutil.copyfile(os.path.join(os.path.dirname(__file__), "emulicious.gbc.ini"), "emu/emulicious/Emulicious.ini")
        #elif model == CGB:
        #    shutil.copyfile(os.path.join(os.path.dirname(__file__), "emulicious.sgb.ini"), "emu/emulicious/Emulicious.ini")
        else:
            return None
        process = subprocess.Popen(["java", "-jar", "Emulicious.jar", "-throttle", "10000", os.path.abspath(rom)], cwd="emu/emulicious")
        forceSquareCornersAsync(self.title_check, timeout=self.CORNER_TIMEOUT)
        return process

    def endProcess(self, p):
        if p is None:
            return
        if self.isProcessAlive(p):
            try:
                p.terminate()
            except Exception:
                pass
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run([
                        "taskkill",
                        "/PID",
                        str(p.pid),
                        "/F",
                        "/T",
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    p.kill()

    def getScreenshot(self):
        screenshot = getScreenshot(self.title_check)
        if screenshot is None:
            return None
        return screenshot.crop((0, screenshot.size[1] - 144, 160, screenshot.size[1]))
