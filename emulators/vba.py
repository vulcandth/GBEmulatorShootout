from util import *
from emulator import Emulator
from test import *
import shutil
import platform


class VBA(Emulator):
    def __init__(self):
        super().__init__("VisualBoyAdvance", "https://sourceforge.net/projects/vba", startup_time=0.6)

    def setup(self):
        download("https://sourceforge.net/projects/vba/files/latest/download", "downloads/vba.zip")
        extract("downloads/vba.zip", "emu/vba")
        setDPIScaling("emu/vba/VisualBoyAdvance.exe")
        shutil.copyfile(os.path.join(os.path.dirname(__file__), "vba.ini"), "emu/vba/vba.ini")
        download("https://gbdev.gg8.se/files/roms/bootroms/sgb_boot.bin", "emu/vba/sgb_boot.bin")
        download("https://gbdev.gg8.se/files/roms/bootroms/cgb_boot.bin", "emu/vba/cgb_boot.bin")
        download("https://gbdev.gg8.se/files/roms/bootroms/dmg_boot.bin", "emu/vba/dmg_boot.bin")

    def startProcess(self, rom, *, model, required_features):
        process = subprocess.Popen(["emu/vba/VisualBoyAdvance-SDL.exe", os.path.abspath(rom)], cwd="emu/vba")
        # Windows 11 can apply rounded corners which leak background pixels into screenshots.
        # Match the SameBoy/Emulicious approach: force square corners once the window exists.
        forceSquareCornersAsync(self.title_check, timeout=15.0)
        return process

    def getScreenshot(self):
        # VBA (SDL build) sometimes reports a 0x0 client rect for the top-level window.
        # The actual render surface is typically a child HWND; capture that instead.
        try:
            import win32gui
        except Exception:
            return None

        hwnd = findWindow(self.title_check)
        if not hwnd:
            return None

        def _capture_client(target_hwnd):
            rect = win32gui.GetClientRect(target_hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            if w <= 0 or h <= 0:
                return None
            pos = win32gui.ClientToScreen(target_hwnd, (rect[0], rect[1]))
            return pyautogui.screenshot(region=(pos[0], pos[1], w, h))

        # Preferred: capture the emulator's client area directly.
        screenshot = _capture_client(hwnd)

        best_child = None
        best_area = 0

        def _enum_child(child_hwnd, _):
            nonlocal best_child, best_area
            try:
                rect = win32gui.GetClientRect(child_hwnd)
                w = rect[2] - rect[0]
                h = rect[3] - rect[1]
                area = w * h
                if w > 0 and h > 0 and area > best_area:
                    best_area = area
                    best_child = child_hwnd
            except Exception:
                pass

        try:
            win32gui.EnumChildWindows(hwnd, _enum_child, None)
        except Exception:
            best_child = None

        if screenshot is None and best_child is not None:
            screenshot = _capture_client(best_child)
        if screenshot is None:
            # Fallback: capture the full window rectangle.
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            if width > 0 and height > 0:
                screenshot = pyautogui.screenshot(region=(left, top, width, height))

        if screenshot is None:
            return None

        w, h = screenshot.size
        if w < 160 or h < 144:
            return None

        # Common case: the emulator renders at an integer scale (2x/3x/4x).
        # In that case, downscale back to native resolution rather than cropping.
        if w % 160 == 0 and h % 144 == 0:
            sx = w // 160
            sy = h // 144
            if sx == sy and sx >= 1:
                try:
                    import PIL.Image
                    out = screenshot.resize((160, 144), resample=PIL.Image.NEAREST)
                    # VBA-SDL often produces a solid black scanline at the very top of the
                    # rendered output. If detected, shift the image up by 1px and replicate
                    # the last row.
                    try:
                        gray = out.convert("L")
                        row0 = set(gray.crop((0, 0, 160, 1)).getdata())
                        row1 = set(gray.crop((0, 1, 160, 2)).getdata())
                        if len(row0) == 1 and next(iter(row0)) == 0 and len(row1) == 1 and next(iter(row1)) != 0:
                            shifted = out.crop((0, 1, 160, 144))
                            fixed = out.copy()
                            fixed.paste(shifted, (0, 0))
                            fixed.paste(shifted.crop((0, 142, 160, 143)), (0, 143))
                            out = fixed
                    except Exception:
                        pass
                    return out
                except Exception:
                    pass

        # Fallback: center-crop.
        x = (w - 160) // 2
        y = (h - 144) // 2
        out = screenshot.crop((x, y, x + 160, y + 144))
        try:
            gray = out.convert("L")
            row0 = set(gray.crop((0, 0, 160, 1)).getdata())
            row1 = set(gray.crop((0, 1, 160, 2)).getdata())
            if len(row0) == 1 and next(iter(row0)) == 0 and len(row1) == 1 and next(iter(row1)) != 0:
                shifted = out.crop((0, 1, 160, 144))
                fixed = out.copy()
                fixed.paste(shifted, (0, 0))
                fixed.paste(shifted.crop((0, 142, 160, 143)), (0, 143))
                out = fixed
        except Exception:
            pass
        return out


class VBAM(Emulator):
    def __init__(self):
        super().__init__("VisualBoyAdvance-M", "https://vba-m.com/", startup_time=1.0)
        self.title_check = lambda title: "VisualBoyAdvance-M" in title

    def setup(self):
        def pe_machine_hex(path):
            # Returns PE machine type as int (e.g., 0x8664 x64, 0xAA64 arm64, 0x014C x86)
            with open(path, "rb") as f:
                data = f.read(0x2000)
            if len(data) < 0x40 or data[0:2] != b"MZ":
                return None
            e_lfanew = int.from_bytes(data[0x3C:0x40], "little", signed=False)
            if e_lfanew + 6 >= len(data):
                return None
            if data[e_lfanew:e_lfanew + 4] != b"PE\x00\x00":
                return None
            return int.from_bytes(data[e_lfanew + 4:e_lfanew + 6], "little", signed=False)

        host = platform.machine().casefold()
        if host in {"arm64", "aarch64"}:
            desired = "arm64"
        elif host in {"amd64", "x86_64"}:
            desired = "x64"
        else:
            desired = "x86"

        def asset_filter(name):
            n = name.casefold()
            if not n.endswith(".zip"):
                return False
            if "win" not in n and "windows" not in n:
                return False

            is_arm = any(tok in n for tok in ["arm64", "aarch64", "arm-"])
            is_x64 = any(tok in n for tok in ["x64", "amd64", "x86_64", "win64"]) and not any(tok in n for tok in ["arm64", "aarch64"])
            is_x86 = "x86" in n and "x64" not in n and "win64" not in n and not is_arm

            if desired == "arm64":
                return is_arm
            if desired == "x64":
                return is_x64
            return is_x86

        def ensure_install():
            downloadGithubRelease(
                "visualboyadvance-m/visualboyadvance-m",
                "downloads/vba-m.zip",
                filter=asset_filter,
            )
            extract("downloads/vba-m.zip", "emu/vba-m")

        ensure_install()

        exe_path = "emu/vba-m/visualboyadvance-m.exe"
        machine = pe_machine_hex(exe_path) if os.path.exists(exe_path) else None
        wrong_arch = False
        if desired == "x64" and machine not in (0x8664, 0x014C):
            wrong_arch = True
        if desired == "arm64" and machine != 0xAA64:
            wrong_arch = True
        if desired == "x86" and machine != 0x014C:
            wrong_arch = True

        if wrong_arch:
            # Clean and retry with a stricter filter (common: ARM64 zip on x64 host).
            try:
                shutil.rmtree("emu/vba-m", ignore_errors=True)
            except Exception:
                pass
            try:
                os.remove("downloads/vba-m.zip")
            except Exception:
                pass
            ensure_install()

        setDPIScaling("emu/vba-m/visualboyadvance-m.exe")
        download("https://gbdev.gg8.se/files/roms/bootroms/dmg_boot.bin", "emu/vba-m/dmg_boot.bin")
        download("https://gbdev.gg8.se/files/roms/bootroms/cgb_boot.bin", "emu/vba-m/cgb_boot.bin")
        download("https://gbdev.gg8.se/files/roms/bootroms/sgb_boot.bin", "emu/vba-m/sgb_boot.bin")

        # disables "check for updates" modal window
        subprocess.run([
            "REG",
            "ADD",
            r"HKCU\SOFTWARE\visualboyadvance-m\VisualBoyAdvance-M\WinSparkle",
            "/V",
            "CheckForUpdates",
            "/T",
            "REG_SZ",
            "/D",
            "0",
            "/F",
        ])
        subprocess.run([
            "REG",
            "ADD",
            r"HKCU\SOFTWARE\visualboyadvance-m\VisualBoyAdvance-M\WinSparkle",
            "/V",
            "DidRunOnce",
            "/T",
            "REG_SZ",
            "/D",
            "1",
            "/F",
        ])


    def startProcess(self, rom, *, model, required_features):
        if model == DMG:
            shutil.copyfile(os.path.join(os.path.dirname(__file__), "vbam.dmg.ini"), "emu/vba-m/vbam.ini")
        elif model == CGB:
            shutil.copyfile(os.path.join(os.path.dirname(__file__), "vbam.gbc.ini"), "emu/vba-m/vbam.ini")
        elif model == SGB:
            shutil.copyfile(os.path.join(os.path.dirname(__file__), "vbam.sgb.ini"), "emu/vba-m/vbam.ini")
        else:
            return None
        return subprocess.Popen(["emu/vba-m/visualboyadvance-m.exe", os.path.abspath(rom)], cwd="emu/vba-m")

    def getScreenshot(self):
        screenshot = getScreenshot(self.title_check)
        if screenshot is None:
            return None
        x = (screenshot.size[0] - 160) // 2
        y = (screenshot.size[1] - 144) // 2
        return screenshot.crop((x, y, x + 160, y + 144))
