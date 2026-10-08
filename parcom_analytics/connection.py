"""Qt background jobs for login, read-only refresh and best-effort logout."""

import logging
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from threading import Event

from PySide6.QtCore import QObject, QThread, Signal

from .live_data import fetch_live, load_history, commit_live
from .znuny import ZnunyClient, ZnunyError

LOGGER = logging.getLogger(__name__)


class NetworkWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    progress = Signal(int)

    def __init__(self, client, operation, argument=None, parent=None, cache=None):
        super().__init__(parent)
        self.client, self.operation, self.argument = client, operation, argument
        self.cancel = Event()
        self.cache = cache

    def run(self):
        argument, self.argument = self.argument, None
        try:
            if self.operation == "login":
                self.client.login(*argument)
                argument = None
                result = None
            elif self.operation == "refresh":
                context = self.client.timings.measure("UsableData") if isinstance(self.client, ZnunyClient) else nullcontext()
                lock = self.client._refresh_lock if isinstance(self.client, ZnunyClient) else nullcontext()
                with lock, context:
                    batch = fetch_live(self.client, argument, self.cancel, self.progress.emit, commit=False)
                    result = self._publish(batch)
            elif self.operation == "history":
                lock = self.client._refresh_lock if isinstance(self.client, ZnunyClient) else nullcontext()
                with lock:
                    batch = load_history(self.client, argument, self.cancel, self.progress.emit)
                    result = self._publish(batch)
            elif self.operation == "check":
                stamp = datetime.fromisoformat(argument).astimezone(timezone.utc)-timedelta(seconds=1)
                result = bool(self.client.search_tickets({"TicketLastChangeTimeNewerDate":stamp.strftime("%Y-%m-%d %H:%M:%S"),
                                                         "SearchInArchive":"AllTickets"},limit=1))
            else:
                self.client.logout()
                result = None
            self.succeeded.emit(result)
        except ZnunyError as error:
            self.client.connected = False
            LOGGER.warning("Znuny %s failed: %s", self.operation, type(error).__name__)
            self.failed.emit(str(error))
        except Exception as error:
            LOGGER.error("Znuny %s failed: %s", self.operation, type(error).__name__)
            self.client.connected = False
            self.failed.emit("Die Daten konnten nicht vollständig geladen werden.")
        finally:
            argument = None

    def _publish(self, batch):
        if self.cancel.is_set():
            raise ZnunyError("Laden abgebrochen.")
        context = self.client.timings.measure("AnalyticsAndCache") if isinstance(self.client, ZnunyClient) else nullcontext()
        lock = self.client._lock if isinstance(self.client, ZnunyClient) else nullcontext()
        with lock, context:
            if isinstance(self.client, ZnunyClient) and batch._state is not None and batch._state.generation != self.client._generation:
                raise ZnunyError("Die Znuny-Sitzung hat sich geändert. Bitte erneut laden.")
            if self.cache:
                self.cache.update(batch, cancel=self.cancel)
                result = self.cache.reports()
            else:
                result = batch
            commit_live(self.client, batch)
            return result


class ConnectionController(QObject):
    stateChanged = Signal(str)
    loggedIn = Signal()
    loggedOut = Signal()
    loaded = Signal(object)
    failed = Signal(str)
    busyChanged = Signal(bool)
    progress = Signal(int)
    changesDetected = Signal(bool)

    def __init__(self, parent=None, client=None, cache=None):
        super().__init__(parent)
        self.client = client or ZnunyClient()
        self.cache = cache
        self.worker = None
        self.state = "offline"
        self._logout_pending = False
        self._refresh_pending = None
        self._history_pending = False

    def _set_state(self, state):
        self.state = state
        self.stateChanged.emit(state)

    def _start(self, operation, argument=None):
        if self.worker:
            return
        self.worker = NetworkWorker(self.client, operation, argument, self, self.cache)
        self.worker.succeeded.connect(self._success)
        self.worker.failed.connect(self._failure)
        self.worker.progress.connect(self.progress)
        self.worker.finished.connect(self._finished)
        if operation != "check":
            self._set_state("connecting" if operation != "logout" else "offline")
            self.busyChanged.emit(True)
        self.worker.start()

    def login(self, username, password):
        self._start("login", (username, password))

    def refresh(self, period):
        if self.worker and self.worker.operation in ("check", "history"):
            self._refresh_pending = period
            return
        self._start("refresh", period)

    def load_history(self):
        if not self.cache or not self.cache.batch or self.cache.batch.history_loaded:
            return
        if self.state != "online" and not self.worker:
            return
        if self.worker:
            self._history_pending = True
            return
        # A restored disk snapshot has no raw ticket cache. Refresh it first.
        if self.cache.batch._state is None:
            self._history_pending = True
            self._start("refresh", self.cache.batch.period)
        else:
            self._start("history", self.cache.batch)

    def check_changes(self):
        if self.state == "online" and self.worker is None and self.cache and self.cache.batch:
            batch = self.cache.batch
            self._start("check", batch.load_started_at or batch.captured_at)

    def logout(self):
        self._history_pending = False
        self._refresh_pending = None
        self._set_state("offline")
        if self.worker:
            self._logout_pending = True
            self.worker.cancel.set()
        else:
            self._start("logout")

    def _success(self, result):
        if self._logout_pending:
            return
        if self.worker.operation == "logout":
            self._set_state("offline")
            self.loggedOut.emit()
        elif self.worker.operation == "check":
            self.changesDetected.emit(result)
        else:
            self._set_state("online")
            if self.worker.operation == "login":
                self.loggedIn.emit()
            else:
                self.loaded.emit(result)

    def _failure(self, message):
        self._history_pending = False
        self._refresh_pending = None
        self._set_state("offline")
        if not self._logout_pending:
            self.failed.emit(message)

    def _finished(self):
        worker, self.worker = self.worker, None
        worker.deleteLater()
        if worker.operation != "check":
            self.busyChanged.emit(False)
        if self._logout_pending:
            self._logout_pending = False
            self._start("logout")
        elif self._refresh_pending is not None and self.state == "online":
            period, self._refresh_pending = self._refresh_pending, None
            self._start("refresh",period)
        elif self._history_pending and self.state == "online":
            self._history_pending = False
            self.load_history()
