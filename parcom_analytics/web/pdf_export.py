"""Qt-free launcher for the private, separately packaged PDF renderer."""
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile


def run_export(path, report):
    with tempfile.TemporaryDirectory(prefix="parcom-pdf-") as directory:
        request = Path(directory) / "request.pickle"
        with request.open("wb") as stream:
            pickle.dump((path, report), stream)
        if getattr(sys, "frozen", False):
            worker = Path(sys.executable).parent / "pdf_worker" / "ParCom_PDF_Worker.exe"
            command = [str(worker), str(request)]
        else:
            command = [sys.executable, "-m", "parcom_analytics.web.pdf_worker", str(request)]
        environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "MPLBACKEND": "Agg"}
        # The main bootloader changes Windows' DLL search directory. Reset it in
        # this dedicated child bootloader; never change the running host's loader.
        environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        if sys.platform == "win32":
            environment["PATH"] = os.pathsep.join((str(Path(sys.executable).parent),
                                                   str(Path(os.environ["SystemRoot"]) / "System32"),
                                                   os.environ["SystemRoot"]))
            for key in ("QT_PLUGIN_PATH", "QML2_IMPORT_PATH"):
                environment.pop(key, None)
        subprocess.run(command, env=environment, check=True, capture_output=True, timeout=180,
                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
