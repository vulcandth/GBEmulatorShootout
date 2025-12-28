import time
import os
import PIL.Image
from collections import namedtuple

from util import *


TestResult = namedtuple('TestResult', ['result', 'screenshot', 'startuptime', 'runtime'])

class Emulator:
    def __init__(self, name, url, *, startup_time=1.0, features=None):
        self.name = name
        self.url = url
        self.startup_time = startup_time
        self.title_check = lambda title: title.startswith(self.name)
        self.speed = 1.0
        self.features = features or set()

    def setup(self):
        raise NotImplementedError()

    def startProcess(self, rom, *, model, required_features):
        raise NotImplementedError()

    def postWindowCreation(self):
        pass

    def getScreenshot(self):
        return getScreenshot(self.title_check)

    def isWindowOpen(self):
        return findWindow(self.title_check) is not None

    def isProcessAlive(self, p):
        return p.poll() is None

    def processOutput(self, p):
        # Best-effort crash info. If stdout/stderr are piped and the process has exited,
        # capture them once so callers can include helpful diagnostics.
        rc = p.poll()
        if rc is None:
            return None

        cached = getattr(p, "_gbshootout_output", None)
        if cached is not None:
            return cached

        out = None
        err = None
        try:
            if getattr(p, "stdout", None) is not None or getattr(p, "stderr", None) is not None:
                out, err = p.communicate(timeout=0.2)
        except Exception:
            out, err = None, None

        def _to_text(v):
            if v is None:
                return None
            if isinstance(v, bytes):
                try:
                    return v.decode("utf-8", errors="replace")
                except Exception:
                    return repr(v)
            return str(v)

        out = _to_text(out)
        err = _to_text(err)
        if out or err:
            msg = ""
            if err:
                msg += f"stderr:\n{err.strip()}\n"
            if out:
                msg += f"stdout:\n{out.strip()}\n"
            msg = msg.strip()
            setattr(p, "_gbshootout_output", msg)
            return msg

        setattr(p, "_gbshootout_output", rc)
        return rc

    def endProcess(self, p):
        p.terminate()

    def undoSetup(self):
        pass

    def returncode(self, p):
        return p.returncode

    def run(self, test):
        print("Running %s on %s" % (test, self))

        sav_file = os.path.splitext(test.rom)[0] + ".sav"
        if os.path.exists(sav_file):
            os.unlink(sav_file)

        p = self.startProcess(test.rom, model=test.model, required_features=test.required_features)
        if p is None:
            print("%s cannot run %s (incompattible model or feature requests)" % (self, test))
            return None
        process_create_time = time.monotonic()
        while not self.isWindowOpen():
            time.sleep(0.01)
            if not self.isProcessAlive(p):
                details = self.processOutput(p)
                raise AssertionError(f"Process crashed? (exit: {self.returncode(p)})" + (f"\n{details}" if details else ""))
            assert time.monotonic() - process_create_time < 30.0, "Creating the window took longer then 30 seconds?"
        process_create_time = time.monotonic() - process_create_time
        self.postWindowCreation()
        start_time = time.monotonic()
        result = None
        screenshot = None
        while time.monotonic() - start_time < (test.runtime / self.speed) + self.startup_time + 5.0:
            time.sleep(0.1)
            screenshot = self.getScreenshot()
            if screenshot is not None:
                result = test.checkResult(screenshot)
                if result is not None:
                    print("Early exit: %s: %g" % (result, time.monotonic() - start_time))
                    break
            if not self.isProcessAlive(p):
                details = self.processOutput(p)
                raise AssertionError(f"Process crashed? (exit: {self.returncode(p)})" + (f"\n{details}" if details else ""))
        self.endProcess(p)
        if result is None:
            result = test.getDefaultResult()
        return TestResult(result=result, screenshot=screenshot, startuptime=process_create_time, runtime=time.monotonic()-start_time)

    def getRunTimeFor(self, test):
        p = self.startProcess(test.rom, model=test.model, required_features=test.required_features)
        if p is None:
            return None
        while not self.isWindowOpen():
            time.sleep(0.01)
            assert self.isProcessAlive(p), "Process crashed?"
        time.sleep(self.startup_time)
        start = time.monotonic()
        last_change = time.monotonic()
        prev = None
        while True:
            time.sleep(0.1)
            screenshot = self.getScreenshot()
            if prev is not None and not compareImage(screenshot, prev):
                last_change = time.monotonic()
            prev = screenshot
            if time.monotonic() - last_change > 10.0:
                break
            assert self.isProcessAlive(p), "Process crashed? (exit: %d)" % (self.returncode(p))
        if not os.path.exists(test.pass_result_filename):
            screenshot.save(test.pass_result_filename)
        self.endProcess(p)
        return last_change - start

    def measureStartupTime(self, *, model):
        print(f'Measuring startup time of {self}')
        p = self.startProcess("startup_time_test.gb", model=model, required_features=set())
        if p is None:
            return None, None
        reference = PIL.Image.open("startup_time_test.png")
        start_pre_window_time = time.monotonic()
        while not self.isWindowOpen():
            time.sleep(0.01)
            if not self.isProcessAlive(p) or time.monotonic() - start_pre_window_time > 60.0:
                screenshot = fullscreenScreenshot()
                print("Window not found")
                if self.isProcessAlive(p):
                    print("Process timeout: %s" % (self.processOutput(p)))
                    self.endProcess(p)
                else:
                    print("Process gone: %s" % (self.processOutput(p)))
                return None, screenshot
        post_window_time = time.monotonic()
        print("Window found")
        while True:
            if not self.isProcessAlive(p) or time.monotonic() - post_window_time > 60.0:
                screenshot = fullscreenScreenshot()
                if self.isProcessAlive(p):
                    print("Process timeout: %s" % (self.processOutput(p)))
                    self.endProcess(p)
                else:
                    print("Process gone: %s" % (self.processOutput(p)))
                return None, screenshot
            screenshot = self.getScreenshot()
            if screenshot is None:
                continue
            if screenshot.size[0] != 160 or screenshot.size[1] != 144:
                continue
            colors = screenshot.getcolors()
            if colors is None or len(colors) != 2:
                continue
            if not compareImage(screenshot, reference):
                continue
            break
        startup_time = time.monotonic() - post_window_time
        screenshot = fullscreenScreenshot()
        self.endProcess(p)
        return startup_time, screenshot

    def getJsonFilename(self):
        return "%s.json" % (self.name.replace(" ", "_").lower())

    def __repr__(self):
        return self.name
