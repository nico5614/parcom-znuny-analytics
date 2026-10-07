"""Smoke-test the frozen Windows runtime without using real data or a server."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import pefile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from parcom_analytics import VERSION


def main():
    exe = ROOT / "dist" / "ParCom_Znuny_Analytics" / "ParCom_Znuny_Analytics.exe"
    with pefile.PE(str(exe)) as binary:
        assert binary.OPTIONAL_HEADER.Subsystem == 2, "Unexpected console executable"
    with tempfile.TemporaryDirectory(prefix="parcom-bundle-") as temporary:
        environment = os.environ.copy()
        environment.update(LOCALAPPDATA=temporary, QT_QPA_PLATFORM="offscreen",
                           PATH=str(Path(os.environ["WINDIR"]) / "System32"))
        for name in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
            environment.pop(name, None)
        data = Path(temporary) / "ParCom" / "ZnunyAnalytics"
        process = subprocess.Popen([str(exe)], cwd=exe.parent, env=environment,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline and process.poll() is None:
                if (data / "index.json").exists():
                    break
                time.sleep(.2)
            assert process.poll() is None, "Frozen application exited during startup"
            assert (data / "index.json").exists(), "Frozen application did not initialize storage"
            log = (data / "logs" / "app.log").read_text(encoding="utf-8")
            assert f"Starting ParCom Znuny Analytics {VERSION}" in log
            time.sleep(1)
            assert process.poll() is None, "Frozen application exited after initialization"
        finally:
            if process.poll() is None:
                # This isolated, offline process has no session or customer data.
                process.terminate()
            process.wait(timeout=10)
    print("Frozen EXE startup passed with isolated storage and no Python on PATH.")


if __name__ == "__main__":
    main()
