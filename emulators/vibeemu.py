from util import *
from emulator import Emulator
from test import *
import os
import subprocess
import PIL.Image
import PIL.ImageOps


class VibeEmu(Emulator):
    def __init__(self):
        super().__init__("vibeEmu", "https://github.com/vulcandth/vibeEmu", startup_time=1.0)
        self.title_check = lambda title: "vibeEmu" in title

    def setup(self):
        download("https://codeload.github.com/vulcandth/vibeEmu/zip/main", "downloads/vibeemu.zip")
        extract("downloads/vibeemu.zip", "emu/vibeemu")
        self.path = os.path.join("emu", "vibeemu", os.listdir("emu/vibeemu")[0])
        subprocess.Popen(["cargo", "build"], cwd=self.path).wait()
        self.exe = os.path.join(self.path, "target", "debug", "vibeEmu.exe")
        setDPIScaling(self.exe)
        setupMesa(os.path.dirname(self.exe))

    def startProcess(self, rom, *, model, required_features):
        mode = {DMG: "--dmg", CGB: "--cgb"}.get(model)
        if mode is None:
            return None
        return subprocess.Popen([self.exe, mode, os.path.abspath(rom)], cwd=self.path)

    def getScreenshot(self):
        screenshot = super().getScreenshot()
        if screenshot is None:
            return None
        screenshot = screenshot.resize((160, 144), PIL.Image.NEAREST)
        screenshot = screenshot.convert(mode="L", dither=PIL.Image.NONE)
        screenshot = PIL.ImageOps.autocontrast(screenshot)
        return screenshot
