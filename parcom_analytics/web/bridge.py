"""Narrow explicit JS API. Private attributes must never be exposed by pywebview."""

from datetime import datetime, timezone
from threading import Event, Lock
import platform
import sys

from .. import APP_NAME, VERSION
from .serialization import json_value


class DesktopBridge:
    def __init__(self, publish=lambda event: None):
        self._publish = publish
        self._lock = Lock()
        self._probe_sequence = 0
        self._probe_confirmed = Event()

    def getAppInfo(self):
        return {"name": APP_NAME, "version": VERSION, "python": platform.python_version(),
                "renderer": "Windows WebView2", "packaged": bool(getattr(sys, "frozen", False))}

    def probe(self):
        with self._lock:
            self._probe_sequence += 1
            sequence = self._probe_sequence
        self._publish({"kind": "probe", "sequence": sequence,
                       "message": "React ↔ Python verbunden. Lokale Assets geladen."})
        return json_value({"sequence": sequence, "sentAt": datetime.now(timezone.utc)})

    def confirmProbe(self, sequence):
        if type(sequence) is int and sequence == self._probe_sequence and sequence > 0:
            self._probe_confirmed.set()
            return True
        return False
