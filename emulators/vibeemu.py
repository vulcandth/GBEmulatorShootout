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
        # Startup times (measured locally): DMG ~5.594s, CGB ~2.984s
        super().__init__("vibeEmu", "https://github.com/vulcandth/vibeEmu", startup_time=6, features=(PCM,))
        # The actual window title is "vibeEmu" (and "vibeEmu – ..." for auxiliary windows).
        # Keep this strict to avoid accidentally matching VS Code/editor windows.
        self.title_check = lambda title: bool(title) and title.startswith("vibeEmu")
        self._debug_screenshot_saved = 0
        self._dmg_bootrom = None
        self._cgb_bootrom = None

    def setup(self):
        # By default, avoid re-downloading and re-compiling locally to speed up
        # iterative development. Force a fresh download/build in CI or when the
        # `VIBEEMU_REBUILD` env var is set.
        force_rebuild = os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS") or os.environ.get("VIBEEMU_REBUILD")
        downloads_zip = "downloads/vibeemu.zip"
        extracted_root = os.path.join("emu", "vibeemu")

        if force_rebuild:
            if os.path.exists(downloads_zip):
                os.unlink(downloads_zip)
            if os.path.exists(extracted_root):
                shutil.rmtree(extracted_root)

        # If we've already extracted the source tree locally and aren't forcing
        # a rebuild, reuse it to avoid unnecessary downloads/compiles.
        if not os.path.exists(extracted_root) or force_rebuild:
            download("https://codeload.github.com/vulcandth/vibeEmu/zip/main", downloads_zip)
            extract(downloads_zip, extracted_root)

        # Find the extracted source directory (prefer a subdir containing Cargo.toml)
        self.path = None
        if os.path.exists(extracted_root):
            for name in os.listdir(extracted_root):
                candidate = os.path.join(extracted_root, name)
                if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, "Cargo.toml")):
                    self.path = candidate
                    break
            if self.path is None:
                # fallback to first directory entry
                for name in os.listdir(extracted_root):
                    candidate = os.path.join(extracted_root, name)
                    if os.path.isdir(candidate):
                        self.path = candidate
                        break
        if self.path is None:
            raise FileNotFoundError(f"Could not locate vibeEmu source tree under {extracted_root}")

        # Use the same public boot ROMs that SameBoy uses.
        bootrom_dir = os.path.join("emu", "vibeemu", "bootroms")
        os.makedirs(bootrom_dir, exist_ok=True)
        self._cgb_bootrom = os.path.join(bootrom_dir, "cgb_boot.bin")
        self._dmg_bootrom = os.path.join(bootrom_dir, "dmg_boot.bin")
        download("https://gbdev.gg8.se/files/roms/bootroms/cgb_boot.bin", self._cgb_bootrom)
        download("https://gbdev.gg8.se/files/roms/bootroms/dmg_boot.bin", self._dmg_bootrom)

        # Only build if the release exe doesn't already exist or if rebuilding
        self.exe = os.path.join(self.path, "target", "release", "vibe-emu-ui.exe")
        if force_rebuild or not os.path.exists(self.exe):
            subprocess.Popen(["cargo", "build", "--release"], cwd=self.path).wait()
        if not os.path.exists(self.exe):
            raise FileNotFoundError(f"Expected executable not found: {self.exe}")
        setDPIScaling(self.exe)
        setupMesa(os.path.dirname(self.exe))

    def startProcess(self, rom, *, model, required_features):
        if model == DMG:
            self.startup_time = 5.594
            args = [self.exe, "--dmg", "--dmg-neutral"]
            if self._dmg_bootrom and os.path.exists(self._dmg_bootrom):
                args += ["--bootrom", os.path.abspath(self._dmg_bootrom)]
            args += [os.path.abspath(rom)]
        elif model == CGB:
            self.startup_time = 2.984
            args = [self.exe, "--cgb"]
            if self._cgb_bootrom and os.path.exists(self._cgb_bootrom):
                args += ["--bootrom", os.path.abspath(self._cgb_bootrom)]
            args += [os.path.abspath(rom)]
        else:
            return None

        # Optional debug: print the exact args used to launch the emulator.
        if os.environ.get("VIBEEMU_DEBUG_ARGS"):
            print("vibeEmu launch:", args)

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
        # vibeEmu renders the GB framebuffer with integer scaling in logical pixels.
        # On Windows with DPI scaling, the captured client-area pixels can be a
        # fractional multiple of 160x144 (e.g. 2x * 125% = 2.5x).
        # Instead of assuming 2x (320x288), infer the framebuffer size from the
        # client width and the GB aspect ratio (10:9), then crop from the bottom
        # to exclude the menu bar.

        crop_w = width
        crop_h = int(round(crop_w * (target_h / target_w)))
        if crop_h <= 0:
            return None
        if crop_h > height:
            # If the window isn't tall enough for the inferred aspect, fall back
            # to the largest possible crop that preserves the GB aspect.
            crop_h = height
            crop_w = int(round(crop_h * (target_w / target_h)))
            crop_w = min(crop_w, width)

        bottom = height
        top = max(bottom - crop_h, 0)
        left = max((width - crop_w) // 2, 0)
        right = min(left + crop_w, width)
        frame = screenshot.crop((left, top, right, bottom))
        if frame.size != (target_w, target_h):
            frame = frame.resize((target_w, target_h), PIL.Image.NEAREST)

        frame = frame.convert("RGB")

        if should_save and tag:
            try:
                crop_debug = f"cropbox=({left},{top})-({right},{bottom})"
                if os.environ.get("VIBEEMU_DEBUG_SCREENSHOT_VERBOSE"):
                    print(f"vibeEmu screenshot: raw={screenshot.size} {crop_debug} cropped={frame.size}")
                cropped_path = os.path.join(debug_dir, f"cropped-{tag}-{frame.size[0]}x{frame.size[1]}.png")
                frame.save(cropped_path)
            except Exception:
                pass
            finally:
                self._debug_screenshot_saved += 1

        return frame
