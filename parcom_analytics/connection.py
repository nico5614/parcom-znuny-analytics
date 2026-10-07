"""Qt background jobs for login, read-only refresh and best-effort logout."""

import logging
from threading import Event

from PySide6.QtCore import QObject, QThread, Signal

from .live_data import fetch_live
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
                result = fetch_live(self.client, argument, self.cancel, self.progress.emit)
                if self.cancel.is_set():
                    raise ZnunyError("Laden abgebrochen.")
                if self.cache:
                    self.cache.update(result)
                    result = self.cache.reports()
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


class ConnectionController(QObject):
    stateChanged = Signal(str)
    loggedIn = Signal()
    loggedOut = Signal()
    loaded = Signal(object)
    failed = Signal(str)
    busyChanged = Signal(bool)
    progress = Signal(int)

    def __init__(self, parent=None, client=None, cache=None):
        super().__init__(parent)
        self.client = client or ZnunyClient()
        self.cache = cache
        self.worker = None
        self.state = "offline"
        self._logout_pending = False

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
        self._set_state("connecting" if operation != "logout" else "offline")
        self.busyChanged.emit(True)
        self.worker.start()

    def login(self, username, password):
        self._start("login", (username, password))

    def refresh(self, period):
        self._start("refresh", period)

    def logout(self):
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
        else:
            self._set_state("online")
            if self.worker.operation == "login":
                self.loggedIn.emit()
            else:
                self.loaded.emit(result)

    def _failure(self, message):
        self._set_state("offline")
        if not self._logout_pending:
            self.failed.emit(message)

    def _finished(self):
        worker, self.worker = self.worker, None
        worker.deleteLater()
        self.busyChanged.emit(False)
        if self._logout_pending:
            self._logout_pending = False
            self._start("logout")
