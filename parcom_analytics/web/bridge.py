"""Narrow explicit JS API. Private attributes must never be exposed by pywebview."""

from datetime import datetime, timedelta, timezone
from threading import Event, Lock, RLock
import platform
import sys
import re
import webbrowser

from .. import APP_NAME, VERSION
from .serialization import json_value


class DesktopBridge:
    def __init__(self, publish=lambda event: None, client=None, root=None, cache=None, settings=None, fetch=None):
        self._publish = publish
        self._lock = Lock()
        self._probe_sequence = 0
        self._probe_confirmed = Event()
        self._network = Lock()
        self._state_lock = RLock()
        self._client = client
        self._username = None
        self._closing = False
        self._root = root
        self._cache = cache
        self._settings = settings
        self._offline = False
        self._busy = False
        self._changes = False
        self._revision = 0
        self._cancel = Event()
        self._fetch = fetch

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
                self._offline = False
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
        self._cancel.set()
        with self._state_lock:
            self._username = None
            self._offline = False
        with self._network:
            if self._client:
                self._client.logout()
            self._username = None
        return {"ok": True, "data": None}

    def _ensure_data(self):
        from ..storage import default_storage_path
        from ..live_cache import LiveCache
        from .settings import Settings
        with self._state_lock:
            if self._cache is None:
                self._root = self._root or default_storage_path()
                self._root.mkdir(parents=True, exist_ok=True)
                self._cache = LiveCache(self._root)
            if self._settings is None:
                self._settings = Settings(self._root)

    def _state(self):
        self._ensure_data()
        with self._state_lock:
            return {"connection": "online" if self._client and self._client.connected else "cached" if self._cache.batch else "offline",
                    "busy": self._busy, "newData": self._changes, "revision": self._revision,
                    "capturedAt": self._cache.batch.captured_at if self._cache.batch else None,
                    "hasCache": self._cache.batch is not None, "warning": self._cache.warning}

    def getState(self):
        return self._state()

    def getPreferences(self):
        self._ensure_data()
        return {"theme": self._settings.get("web_theme", "dark"), "reducedMotion": self._settings.get("reduce_motion", False)}

    def setPreferences(self, theme, reduced_motion):
        if theme not in ("dark", "light") or type(reduced_motion) is not bool:
            return self._error("validation", "Ungültige Darstellungseinstellung.")
        self._ensure_data()
        self._settings.set({"web_theme": theme, "reduce_motion": reduced_motion})
        return {"ok": True, "data": None}

    def continueOffline(self):
        self._ensure_data()
        if not self._cache.batch:
            return self._error("empty", "Noch kein Datenstand geladen.")
        self.logout()
        self._offline = True
        return {"ok": True, "data": {"username": "Offline"}}

    def _error(self, kind, message):
        return {"ok": False, "error": {"kind": kind, "message": message}}

    def _read(self, operation):
        self._ensure_data()
        if not self._username and not self._offline:
            return self._error("authentication", "Bitte zuerst anmelden oder den lokalen Datenstand öffnen.")
        try:
            with self._state_lock:
                return {"ok": True, "data": json_value(operation())}
        except ValueError as error:
            return self._error("validation", str(error))
        except Exception:
            return self._error("data", "Der Datenstand konnte nicht ausgewertet werden.")

    def getPeriod(self):
        from ..periods import TimeRange
        from .dto import period_dto
        self._ensure_data()
        batch = self._cache.batch
        return period_dto(batch.period) if batch and isinstance(batch.period, TimeRange) else period_dto(TimeRange.preset(), "1W")

    def resolvePeriod(self, selection):
        from .dto import resolve_period, period_dto
        try:
            return {"ok": True, "data": period_dto(resolve_period(selection), selection.get("preset"))}
        except (ValueError, TypeError, KeyError) as error:
            return self._error("validation", str(error) if isinstance(error, ValueError) else "Bitte gültige Von- und Bis-Zeiten eingeben.")

    def getOverview(self):
        from .dto import overview
        return self._read(lambda: overview(self._cache, self._settings) if self._cache.batch else None)

    def getAnalysis(self, kpi, ticket_type=None, page=0):
        from .dto import analysis_dto
        if type(kpi) is not int or kpi not in range(1, 8) or type(page) is not int or page < 0:
            return self._error("validation", "Ungültige Analyseauswahl.")
        return self._read(lambda: analysis_dto(self._cache, kpi, ticket_type, page) if self._cache.batch else None)

    def getTicketDetails(self, ticket_id):
        from .dto import ticket_details
        if not isinstance(ticket_id, str) or not re.fullmatch(r"\d+", ticket_id):
            return self._error("validation", "Ungültiges Ticket.")
        return self._read(lambda: ticket_details(self._cache, ticket_id) if self._cache.batch else None)

    def openTicket(self, ticket_id):
        result = self.getTicketDetails(ticket_id)
        if not result["ok"] or not result["data"]:
            return result
        webbrowser.open("https://znuny.parcom.ch/otrs/index.pl?Action=AgentTicketZoom;TicketID=" + ticket_id)
        return {"ok": True, "data": None}

    def refresh(self, selection):
        from .dto import resolve_period, identities
        from ..live_data import fetch_live
        from ..znuny import ZnunyError
        self._ensure_data()
        if not self._username or not self._client or not self._client.connected:
            return self._error("network", "Bitte mit Znuny verbinden. Der lokale Datenstand bleibt verfügbar.")
        if not self._network.acquire(blocking=False):
            return self._error("busy", "Eine Anfrage läuft bereits.")
        self._cancel.clear()
        self._busy = True
        try:
            period = resolve_period(selection)
            batch = self._fetch(period) if self._fetch else fetch_live(self._client, period, self._cancel)
            if self._cancel.is_set():
                return self._error("cancelled", "Laden abgebrochen.")
            with self._state_lock:
                self._cache.update(batch)
                self._settings.set({"agent_registry": identities(self._cache, self._settings)})
                self._revision += 1
                self._changes = False
                self._busy = False
            return {"ok": True, "data": self._state()}
        except ValueError as error:
            return self._error("validation", str(error))
        except ZnunyError as error:
            self._client.connected = False
            return self._error("network", str(error))
        except Exception:
            return self._error("data", "Die Daten konnten nicht vollständig geladen werden. Der letzte Datenstand bleibt verfügbar.")
        finally:
            self._busy = False
            self._network.release()

    def checkChanges(self):
        from ..znuny import ZnunyError
        self._ensure_data()
        if not self._username or not self._client or not self._client.connected or not self._cache.batch:
            return self._state()
        if not self._network.acquire(blocking=False):
            return self._state()
        try:
            batch = self._cache.batch
            stamp = datetime.fromisoformat(batch.load_started_at or batch.captured_at).astimezone(timezone.utc) - timedelta(seconds=1)
            changed = bool(self._client.search_tickets({"TicketLastChangeTimeNewerDate": stamp.strftime("%Y-%m-%d %H:%M:%S"), "SearchInArchive": "AllTickets"}, limit=1))
            self._changes = self._changes or changed
        except ZnunyError:
            self._client.connected = False
        finally:
            self._network.release()
        return self._state()

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
