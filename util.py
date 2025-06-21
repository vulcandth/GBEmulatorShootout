import pyautogui
import requests
import os
import zipfile
import subprocess
import PIL.Image
import PIL.ImageChops
import io
import base64
from tqdm import tqdm

def setupMesa(path):
    download("https://github.com/pal1000/mesa-dist-win/releases/download/20.3.2/mesa3d-20.3.2-release-msvc.7z", "downloads/mesa.7z")
    extract("downloads/mesa.7z", "downloads/mesa")
    dest = os.path.join(os.path.dirname(__file__), r'downloads\mesa\x64')

    os.system(fr'del "{os.path.join(path, "opengl32.dll")}"')
    os.system(fr'del "{os.path.join(path, "libglapi.dll")}"')
    os.system(fr'mklink "{os.path.join(path, "opengl32.dll")}" "{os.path.join(dest, "opengl32.dll")}"')
    os.system(fr'mklink "{os.path.join(path, "libglapi.dll")}" "{os.path.join(dest, "libglapi.dll")}"')

def download(url, filename, fake_headers=False, max_retries=5):
    import fasteners  # pip install fasteners
    with fasteners.InterProcessLock(filename + ".lock"):
        if os.path.exists(filename):
            return

        os.makedirs(os.path.dirname(filename), exist_ok=True)
        print("Downloading %s" % (url))
        headers = {}
        if fake_headers:
            headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.146 Safari/537.36'

        last_exception = ValueError("max_retries must be greater than 0")

        for _ in range(max_retries):
            try:
                r = requests.get(url, allow_redirects=True, headers=headers, stream=True)

                total_size = int(r.headers.get("Content-Length", 0))

                bar = tqdm(total=total_size, unit='iB', unit_scale=True)

                tempname = filename + '.downloading'
                try:
                    with open(tempname, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1024):
                            f.write(chunk)
                            bar.update(len(chunk))
                    os.rename(tempname, filename)
                    return
                finally:
                    if os.path.exists(tempname):
                        os.remove(tempname)
            except Exception as e:
                last_exception = e
                print("Download failed:", str(e))
                print("Retrying...")

        print("Max retries exceeded. Download failed.")
        raise last_exception

def downloadGithubRelease(repo, filename, *, filter=lambda n: "win" in n, allow_prerelease=False):
    if not os.path.exists(filename):
        if allow_prerelease:
            r = requests.get("https://api.github.com/repos/%s/releases" % (repo))
            data = r.json()[0]
        else:
            r = requests.get("https://api.github.com/repos/%s/releases/latest" % (repo))
            data = r.json()
        url = data["zipball_url"]
        for asset in data["assets"]:
            if filter(asset["name"]):
                url = asset["browser_download_url"]
                break
        download(url, filename)

def _getz7():
    if os.path.exists("c:/Program Files/7-Zip/7z.exe"):
        return "c:/Program Files/7-Zip/7z.exe"
    return "7z"

def extract(filename, path):
    if os.path.exists(path):
        return False
    if filename.endswith(".zip"):
        zipfile.ZipFile(filename).extractall(path)
    elif filename.endswith(".7z") or filename.endswith(".tar.gz"):
        os.makedirs(path, exist_ok=True)
        subprocess.run([_getz7(), "x", os.path.abspath(filename)], cwd=path)
        subprocess.run([_getz7(), "x", os.path.basename(filename)[:-3]], cwd=path)
    elif filename.endswith(".7z"):
        os.makedirs(path, exist_ok=True)
        subprocess.run([_getz7(), "x", os.path.abspath(filename)], cwd=path)
    return True

def findWindow(title_check):
    import win32gui
    def f(hwnd, results):
        title = win32gui.GetWindowText(hwnd)
        if title_check(title):
            results.append(hwnd)
    results = []
    win32gui.EnumWindows(f, results)
    if results:
        return results[0]
    return None

def _captureWindow(hwnd):
    """
    Return a PIL.Image of HWND’s *client* area via Win32 PrintWindow.
    Works even when the window is fully obscured.
    """
    import win32gui, win32ui, win32con, PIL.Image

    left, top, right, bot = win32gui.GetClientRect(hwnd)
    w, h = right - left, bot - top

    hdc_window = win32gui.GetWindowDC(hwnd)
    hdc_src = win32ui.CreateDCFromHandle(hdc_window)
    hdc_mem = hdc_src.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(hdc_src, w, h)
    hdc_mem.SelectObject(bmp)

    win32gui.PrintWindow(hwnd, hdc_mem.GetSafeHdc(), 0)
    bmpinfo = bmp.GetInfo()
    bmpstr = bmp.GetBitmapBits(True)
    img = PIL.Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                               bmpstr, 'raw', 'BGRX', 0, 1)

    win32gui.DeleteObject(bmp.GetHandle())
    hdc_mem.DeleteDC(); hdc_src.DeleteDC(); win32gui.ReleaseDC(hwnd, hdc_window)
    return img

def getScreenshot(title_check):
    import win32gui
    hwnd = findWindow(title_check)
    if not hwnd:
        print("Window not found....")
        def f(hwnd, _):
            title = win32gui.GetWindowText(hwnd)
            if title:
                print(hwnd, title)
        win32gui.EnumWindows(f, None)
        return None
    return _captureWindow(hwnd)

def fullscreenScreenshot():
    return pyautogui.screenshot()

def setDPIScaling(executable):
    subprocess.run(["REG", "ADD", "HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers", "/V", os.path.abspath(executable), "/T", "REG_SZ", "/D", "~ HIGHDPIAWARE", "/F"])

def compareImage(a, b):
    a = a.convert(mode="L", dither=PIL.Image.NONE)
    b = b.convert(mode="L", dither=PIL.Image.NONE)
    result = PIL.ImageChops.difference(a, b)
    for count, color in result.getcolors():
        if color > 50:
            return False
    return True

def imageToBase64(img):
    tmp = io.BytesIO()
    img.save(tmp, "png")
    return base64.b64encode(tmp.getvalue()).decode('ascii')
