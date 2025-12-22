from util import *
from emulator import Emulator
from test import *
import os
import shutil
import subprocess
import time
import PIL.Image


class VibeEmu(Emulator):
    def __init__(self):
        super().__init__("vibeEmu", "https://github.com/vulcandth/vibeEmu", startup_time=1.0, features=(PCM,))
        self.title_check = lambda title: title and "vibe" in title.lower()
        self._debug_screenshot_saved = 0
        self._dmg_bootrom = None
        self._cgb_bootrom = None

    def setup(self):
        # remove any previous download / extracted tree so we always get the latest source
        if os.path.exists("downloads/vibeemu.zip"):
            os.unlink("downloads/vibeemu.zip")
        if os.path.exists(os.path.join("emu", "vibeemu")):
            shutil.rmtree(os.path.join("emu", "vibeemu"))

        download("https://codeload.github.com/vulcandth/vibeEmu/zip/main", "downloads/vibeemu.zip")
        extract("downloads/vibeemu.zip", "emu/vibeemu")
        self.path = os.path.join("emu", "vibeemu", os.listdir("emu/vibeemu")[0])

        # Use the same public boot ROMs that SameBoy uses.
        bootrom_dir = os.path.join("emu", "vibeemu", "bootroms")
        os.makedirs(bootrom_dir, exist_ok=True)
        self._cgb_bootrom = os.path.join(bootrom_dir, "cgb_boot.bin")
        self._dmg_bootrom = os.path.join(bootrom_dir, "dmg_boot.bin")
        download("https://gbdev.gg8.se/files/roms/bootroms/cgb_boot.bin", self._cgb_bootrom)
        download("https://gbdev.gg8.se/files/roms/bootroms/dmg_boot.bin", self._dmg_bootrom)

        subprocess.Popen(["cargo", "build", "--release"], cwd=self.path).wait()
        self.exe = os.path.join(self.path, "target", "release", "vibe-emu-ui.exe")
        if not os.path.exists(self.exe):
            raise FileNotFoundError(f"Expected executable not found: {self.exe}")
        setDPIScaling(self.exe)
        setupMesa(os.path.dirname(self.exe))

    def startProcess(self, rom, *, model, required_features):
        if model == DMG:
            args = [self.exe, "--dmg", "--dmg-neutral"]
            if self._dmg_bootrom and os.path.exists(self._dmg_bootrom):
                args += ["--bootrom", os.path.abspath(self._dmg_bootrom)]
            args += [os.path.abspath(rom)]
        elif model == CGB:
            args = [self.exe, "--cgb"]
            if self._cgb_bootrom and os.path.exists(self._cgb_bootrom):
                args += ["--bootrom", os.path.abspath(self._cgb_bootrom)]
            args += [os.path.abspath(rom)]
        else:
            return None

        return subprocess.Popen(args, cwd=self.path)

    def getScreenshot(self):
        screenshot = super().getScreenshot()
        if screenshot is None:
            return None

        # Optional troubleshooting: save raw + cropped images to disk.
        # Enable with env var, or flip DEBUG_ALWAYS to True temporarily.
        DEBUG_ALWAYS = False
        debug_enabled = DEBUG_ALWAYS or os.environ.get("VIBEEMU_DEBUG_SCREENSHOT", "").strip() not in ("", "0", "false", "False")

        try:
            limit = int(os.environ.get("VIBEEMU_DEBUG_SCREENSHOT_LIMIT", "10"))
        except Exception:
            limit = 10

        should_save = debug_enabled and self._debug_screenshot_saved < max(limit, 0)
        debug_dir = os.environ.get(
            "VIBEEMU_DEBUG_SCREENSHOT_DIR",
            os.path.join("downloads", "debug_screenshots", "vibeemu"),
        )

        tag = None
        if should_save:
            try:
                os.makedirs(debug_dir, exist_ok=True)
                stamp = time.strftime("%Y%m%d-%H%M%S")
                tag = f"{stamp}-{int(time.time() * 1000)}-{self._debug_screenshot_saved:03d}"
                raw_path = os.path.join(debug_dir, f"raw-{tag}-{screenshot.size[0]}x{screenshot.size[1]}.png")
                screenshot.save(raw_path)
            except Exception:
                # Best-effort debugging; don't break test runs.
                tag = None

        width, height = screenshot.size
        target_w, target_h = 160, 144
        # vibeEmu shows a menu/title bar within the client area.
        # The Game Boy framebuffer is displayed at a fixed 2x scale (320x288).
        # Always take the bottom 288 pixels so the menu bar is excluded.
        scale = 2
        crop_w = target_w * scale
        crop_h = target_h * scale
        top = max(height - crop_h, 0)
        bottom = height
        left = max((width - crop_w) // 2, 0)
        right = min(left + crop_w, width)
        frame = screenshot.crop((left, top, right, bottom))
        if frame.size != (target_w, target_h):
            frame = frame.resize((target_w, target_h), PIL.Image.NEAREST)

        frame = frame.convert("RGB")

        if should_save and tag:
            try:
                crop_debug = f"cropbox=({left},{top})-({right},{bottom})"
                print(f"vibeEmu screenshot: raw={screenshot.size} {crop_debug} cropped={frame.size}")
                cropped_path = os.path.join(debug_dir, f"cropped-{tag}-{frame.size[0]}x{frame.size[1]}.png")
                frame.save(cropped_path)
            except Exception:
                pass
            finally:
                self._debug_screenshot_saved += 1

        return frame
