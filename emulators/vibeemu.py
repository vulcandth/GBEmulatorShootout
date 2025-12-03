from util import *
from emulator import Emulator
from test import *
import os
import shutil
import subprocess
import PIL.Image


class VibeEmu(Emulator):
    def __init__(self):
        super().__init__("vibeEmu", "https://github.com/vulcandth/vibeEmu", startup_time=1.0)
        self.title_check = lambda title: title and "vibe" in title.lower()

    def setup(self):
        # remove any previous download / extracted tree so we always get the latest source
        if os.path.exists("downloads/vibeemu.zip"):
            os.unlink("downloads/vibeemu.zip")
        if os.path.exists(os.path.join("emu", "vibeemu")):
            shutil.rmtree(os.path.join("emu", "vibeemu"))

        download("https://codeload.github.com/vulcandth/vibeEmu/zip/main", "downloads/vibeemu.zip")
        extract("downloads/vibeemu.zip", "emu/vibeemu")
        self.path = os.path.join("emu", "vibeemu", os.listdir("emu/vibeemu")[0])
        subprocess.Popen(["cargo", "build", "--release"], cwd=self.path).wait()
        self.exe = os.path.join(self.path, "target", "release", "vibe-emu-ui.exe")
        if not os.path.exists(self.exe):
            raise FileNotFoundError(f"Expected executable not found: {self.exe}")
        setDPIScaling(self.exe)
        setupMesa(os.path.dirname(self.exe))

    def startProcess(self, rom, *, model, required_features):
        if model == DMG:
            args = [self.exe, "--dmg", "--dmg-neutral", os.path.abspath(rom)]
        elif model == CGB:
            args = [self.exe, "--cgb", os.path.abspath(rom)]
        else:
            return None

        return subprocess.Popen(args, cwd=self.path)

    def getScreenshot(self):
        screenshot = super().getScreenshot()
        if screenshot is None:
            return None
        width, height = screenshot.size
        target_w, target_h = 160, 144
        scale = min(max(width // target_w, 1), max(height // target_h, 1))
        crop_w = target_w * scale
        crop_h = target_h * scale
        left = max((width - crop_w) // 2, 0)
        top = max((height - crop_h) // 2, 0)
        frame = screenshot.crop((left, top, left + crop_w, top + crop_h))
        if frame.size != (target_w, target_h):
            frame = frame.resize((target_w, target_h), PIL.Image.NEAREST)
        return frame.convert("RGB")
