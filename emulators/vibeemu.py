from util import *
from emulator import Emulator
from test import *
import os
import re
import shutil
import subprocess
import time
import PIL.Image


# Game Boy LCD refresh rate used by the core.
GB_FPS = 59.7275


class VibeEmu(Emulator):
    def __init__(self):
        # Startup times (measured locally): DMG ~5.594s, CGB ~2.984s
        super().__init__("vibeEmu", "https://github.com/vulcandth/vibeEmu", startup_time=6, features=(PCM,))
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

        # Build the headless renderer that hooks directly into vibe-emu-core.
        render_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vibeemu_render")
        # Update the Cargo.toml dependency path to point at the extracted core crate.
        core_crate_path = os.path.join(os.path.abspath(self.path), "crates", "vibe-emu-core")
        # Use forward slashes for the TOML path value (works on all platforms).
        core_crate_path_toml = core_crate_path.replace("\\", "/")
        cargo_toml = os.path.join(render_dir, "Cargo.toml")
        with open(cargo_toml, "r") as f:
            content = f.read()
        content = re.sub(
            r'(vibe-emu-core\s*=\s*\{\s*path\s*=\s*)"[^"]*"',
            lambda m: m.group(1) + '"' + core_crate_path_toml + '"',
            content,
        )
        with open(cargo_toml, "w") as f:
            f.write(content)

        exe_name = "vibeemu-render.exe" if os.name == "nt" else "vibeemu-render"
        self.render_exe = os.path.join(render_dir, "target", "release", exe_name)

        if force_rebuild or not os.path.exists(self.render_exe):
            subprocess.Popen(["cargo", "build", "--release"], cwd=render_dir).wait()
        if not os.path.exists(self.render_exe):
            raise FileNotFoundError(f"Expected renderer executable not found: {self.render_exe}")

    def startProcess(self, rom, *, model, required_features):
        # Not used in the headless flow, but kept for compatibility.
        return None

    def run(self, test):
        print("Running %s on %s" % (test, self))

        sav_file = os.path.splitext(test.rom)[0] + ".sav"
        if os.path.exists(sav_file):
            os.unlink(sav_file)

        if test.model == SGB:
            print("%s cannot run %s (incompatible model)" % (self, test))
            return None

        model_arg = "dmg" if test.model == DMG else "cgb"

        # Convert test runtime (seconds) + startup overhead to frame count.
        total_seconds = test.runtime + self.startup_time
        total_frames = int(total_seconds * GB_FPS) + 1

        output_png = os.path.join("downloads", "vibeemu_framebuffer.png")
        os.makedirs(os.path.dirname(output_png), exist_ok=True)

        args = [
            self.render_exe,
            os.path.abspath(test.rom),
            os.path.abspath(output_png),
            "--model", model_arg,
            "--frames", str(total_frames),
        ]

        # Use boot ROM for the appropriate model.
        bootrom = self._dmg_bootrom if test.model == DMG else self._cgb_bootrom
        if bootrom and os.path.exists(bootrom):
            args += ["--bootrom", os.path.abspath(bootrom)]

        start_time = time.monotonic()
        p = subprocess.Popen(args)
        rc = p.wait()
        elapsed = time.monotonic() - start_time

        if rc != 0:
            print("vibeEmu renderer exited with code %d" % rc)
            return TestResult(result=test.getDefaultResult(), screenshot=None, startuptime=0, runtime=elapsed)

        # Load the rendered framebuffer PNG.
        try:
            screenshot = PIL.Image.open(output_png).convert("RGB")
        except Exception as e:
            print("Failed to load renderer output: %s" % e)
            return TestResult(result=test.getDefaultResult(), screenshot=None, startuptime=0, runtime=elapsed)

        result = test.checkResult(screenshot)
        if result is None:
            result = test.getDefaultResult()

        return TestResult(result=result, screenshot=screenshot, startuptime=0, runtime=elapsed)

    def measureStartupTime(self, *, model):
        # Headless rendering has no meaningful startup time.
        return 0.0, None
