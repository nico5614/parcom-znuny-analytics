"""Narrow explicit JS API. Private attributes must never be exposed by pywebview."""

from datetime import datetime, timezone
from threading import Event, Lock, RLock
import platform
import sys

from .. import APP_NAME, VERSION
from .serialization import json_value


class DesktopBridge:
    def __init__(self, publish=lambda event: None, client=None):
        self._publish = publish
        self._lock = Lock()
        self._probe_sequence = 0
        self._probe_confirmed = Event()
        self._network = Lock()
        self._state_lock = RLock()
        self._client = client
        self._username = None
        self._closing = False

    def login(self, username, password):
        from ..znuny import ZnunyClient, LoginError, ConnectionError, ZnunyError
        if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
            return {"ok": False, "error": {"kind": "validation", "message": "Bitte Benutzername und Passwort eingeben."}}
        if not self._network.acquire(blocking=False):
            return {"ok": False, "error": {"kind": "busy", "message": "Eine Anfrage läuft bereits."}}
        try:
            if self._closing:
                return {"ok": False, "error": {"kind": "busy", "message": "Die Anwendung wird geschlossen."}}
            if self._client is None:
                self._client = ZnunyClient()
            self._client.login(username.strip(), password)
            with self._state_lock:
                self._username = username.strip()
            return {"ok": True, "data": {"username": self._username}}
        except LoginError:
            return {"ok": False, "error": {"kind": "authentication", "message": "Anmeldung fehlgeschlagen. Bitte Benutzername und Passwort prüfen."}}
        except ConnectionError:
            return {"ok": False, "error": {"kind": "network", "message": "Znuny ist nicht erreichbar. Bitte Netzwerk oder Serververbindung prüfen."}}
        except ZnunyError:
            return {"ok": False, "error": {"kind": "server", "message": "Die Antwort von Znuny konnte nicht verarbeitet werden."}}
        except Exception:
            return {"ok": False, "error": {"kind": "server", "message": "Die Anmeldung konnte nicht abgeschlossen werden."}}
        finally:
            password = None
            self._network.release()

    def logout(self):
        with self._state_lock:
            self._username = None
        with self._network:
            if self._client:
                self._client.logout()
            self._username = None
        return {"ok": True, "data": None}

    def _close(self):
        self._closing = True
        self.logout()

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
