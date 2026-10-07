"""Read-only GenericTicketConnectorREST client; credentials never leave memory."""

import logging
import re
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from copy import deepcopy
from queue import LifoQueue
from threading import Event, RLock
from urllib.parse import quote

import truststore

# Use the native Windows trust store so company-managed/intermediate CAs work
# without disabling TLS verification.
truststore.inject_into_ssl()

import requests

from .performance import Timings

BASE_URL = "https://znuny.parcom.ch/otrs/nph-genericinterface.pl/Webservice/GenericTicketConnectorREST"
DEFAULT_QUEUES = ("PBX", "PBX Intern")
OPEN_TYPES = ("new", "open", "pending reminder", "pending auto")
WAITING_TYPES = ("pending reminder", "pending auto")
SEARCH_LIMIT = 10000
LOGGER = logging.getLogger(__name__)


class ZnunyError(Exception):
    """A sanitized, German user-facing error."""


class LoginError(ZnunyError):
    pass


class ConnectionError(ZnunyError):
    pass


class SessionExpired(ZnunyError):
    pass


class ZnunyClient:
    def __init__(self, transport=None, concurrency=4):
        if type(concurrency) is not int or not 1 <= concurrency <= 6:
            raise ValueError("Concurrency must be between 1 and 6")
        self.concurrency = concurrency
        self._lock = RLock()
        self._generation = 0
        self._inflight = {}
        self.timings = Timings()
        # A requests.Session has mutable cookies. Lease each persistent session
        # exclusively; never share one Session concurrently across worker threads.
        self._sessions = LifoQueue(maxsize=concurrency)
        for _ in range(concurrency):
            http = transport if transport is not None else requests.Session()
            http.trust_env = False
            if transport is None:
                http.mount("https://", requests.adapters.HTTPAdapter(
                    pool_connections=1, pool_maxsize=1, pool_block=True, max_retries=0))
            self._sessions.put(http)
        self._http = http
        self._session_id = None
        self.connected = False

    def _request(self, operation, suffix="", data=None, timeout=(5, 30)):
        with self.timings.measure(operation):
            return self._perform_request(operation, suffix, data, timeout)

    def _perform_request(self, operation, suffix, data, timeout):
        # Routes are intentionally closed: there is no generic write-ticket API.
        method, path = {"SessionCreate": ("POST", "/Session"),
                        "SessionDelete": ("DELETE", "/Session/" + suffix),
                        "SessionGet": ("GET", "/Session/" + suffix),
                        "TicketSearch": ("POST", "/Ticket/Search"),
                        "TicketHistoryGet": ("GET", "/Ticket/History/" + suffix),
                        "TicketGet": ("GET", "/Ticket/" + suffix)}[operation]
        LOGGER.info("Znuny operation: %s", operation)
        with self._lock:
            generation = self._generation
        try:
            request_data = {"params": data} if method == "GET" else ({"json": data} if data is not None else {})
            http = self._sessions.get()
            try:
                with self._lock:
                    if operation.startswith("Ticket") and (generation != self._generation or not self._session_id):
                        raise SessionExpired("Die Znuny-Sitzung ist abgelaufen. Bitte erneut anmelden.")
                response = http.request(method, BASE_URL + path, **request_data,
                                        timeout=timeout, verify=True, allow_redirects=False)
            finally:
                self._sessions.put(http)
            with self._lock:
                if operation.startswith("Ticket") and generation != self._generation:
                    raise SessionExpired("Die Znuny-Sitzung ist abgelaufen. Bitte erneut anmelden.")
            if response.status_code in (401, 403):
                self._auth_error(operation)
            if not 200 <= response.status_code < 300:
                raise ConnectionError("Keine Verbindung zu Znuny möglich.")
            payload = response.json()
            if not isinstance(payload, dict):
                raise ZnunyError("Die Antwort von Znuny konnte nicht verarbeitet werden.")
            if payload.get("Error"):
                error = payload["Error"]
                code = str(error.get("ErrorCode", "")) if isinstance(error, dict) else ""
                if any(word in code.lower() for word in ("auth", "session", "accessdenied")):
                    self._auth_error(operation)
                raise ZnunyError("Die Daten konnten nicht vollständig geladen werden.")
            self.connected = bool(self._session_id)
            return payload
        except (requests.RequestException, ValueError):
            self.connected = False
            raise ConnectionError("Keine Verbindung zu Znuny möglich.") from None
        except ZnunyError:
            self.connected = False
            raise

    def _auth_error(self, operation):
        with self._lock:
            self._session_id = None
            self._generation += 1
        if operation == "SessionCreate":
            raise LoginError("Anmeldung fehlgeschlagen. Benutzername oder Passwort prüfen.")
        raise SessionExpired("Die Znuny-Sitzung ist abgelaufen. Bitte erneut anmelden.")

    def login(self, username, password):
        if self._session_id:
            self.logout()
        try:
            payload = self._request("SessionCreate", data={"UserLogin": username, "Password": password})
            session_id = payload.get("SessionID")
            if not isinstance(session_id, str) or not session_id:
                raise LoginError("Anmeldung fehlgeschlagen. Benutzername oder Passwort prüfen.")
            self._session_id = session_id
            self.connected = True
            LOGGER.info("Znuny login successful")
        finally:
            password = None
            username = None

    def _auth(self):
        if not self._session_id:
            raise SessionExpired("Die Znuny-Sitzung ist abgelaufen. Bitte erneut anmelden.")
        return {"SessionID": self._session_id}

    def logout(self):
        with self._lock:
            session_id, self._session_id = self._session_id, None
            self._generation += 1
            self.connected = False
        try:
            if session_id:
                self._request("SessionDelete", quote(session_id, safe=""), timeout=(1, 2))
        except ZnunyError:
            LOGGER.warning("Znuny session cleanup unsuccessful")
        finally:
            session_id = None
            self.connected = False

    def search_tickets(self, filters=None, limit=SEARCH_LIMIT):
        payload = self._request("TicketSearch", data={**(filters or {}), **self._auth(), "Queues": list(DEFAULT_QUEUES),
                                "Limit": limit})
        ids = payload.get("TicketIDs", payload.get("TicketID", []))
        if ids is None:
            ids = []
        if isinstance(ids, (str, int)):
            ids = [ids]
        if not isinstance(ids, list) or any(not re.fullmatch(r"\d+", str(value)) for value in ids):
            raise ZnunyError("Die Ticketliste von Znuny ist ungültig.")
        return list(dict.fromkeys(str(value) for value in ids))

    def get_ticket(self, ticket_id):
        return self.get_tickets([ticket_id])[0]

    def _shared(self, operation, ticket_id, load, cancel=None):
        with self._lock:
            key = (self._generation, operation, ticket_id)
            future = self._inflight.get(key)
            owner = future is None
            if owner:
                future = self._inflight[key] = Future()
        if owner:
            try:
                future.set_result(load())
            except BaseException as error:
                future.set_exception(error)
            finally:
                with self._lock:
                    self._inflight.pop(key, None)
        while True:
            if cancel is not None and cancel.is_set():
                raise ZnunyError("Laden abgebrochen.")
            try:
                # Consumers can safely annotate their own returned data.
                return deepcopy(future.result(timeout=.05))
            except TimeoutError:
                continue

    def get_tickets(self, ticket_ids, cancel=None):
        ids = [str(value) for value in ticket_ids]
        if not ids or len(ids) > 50 or any(not re.fullmatch(r"\d+", value) for value in ids):
            raise ValueError("Invalid ticket ID")
        stopped = Event()

        def fetch(ticket_id):
            if stopped.is_set() or (cancel is not None and cancel.is_set()):
                raise ZnunyError("Laden abgebrochen.")
            try:
                return self._shared("TicketGet", ticket_id, lambda: self._get_ticket(ticket_id), cancel)
            except BaseException:
                stopped.set()
                raise

        unique = list(dict.fromkeys(ids))
        if len(unique) == 1:
            items = [fetch(unique[0])]
        else:
            with ThreadPoolExecutor(max_workers=self.concurrency, thread_name_prefix="znuny") as pool:
                # At most one small batch is queued; map preserves input order.
                items = list(pool.map(fetch, unique, buffersize=self.concurrency))
        if cancel is not None and cancel.is_set():
            raise ZnunyError("Laden abgebrochen.")
        tickets = dict(zip(unique, items))
        return [deepcopy(tickets[ticket_id]) for ticket_id in ids]

    def _get_ticket(self, ticket_id):
        payload = self._request("TicketGet", ticket_id, data={**self._auth(), "Extended": 1,
                                "AllArticles": 0, "Attachments": 0, "DynamicFields": 0})
        item = payload.get("Ticket")
        if isinstance(item, list):
            item = item[0] if len(item) == 1 else None
        if not isinstance(item, dict) or str(item.get("TicketID")) != ticket_id:
            raise ZnunyError("Die Ticketantwort von Znuny ist ungültig.")
        return item

    def get_history(self, ticket_id):
        if not re.fullmatch(r"\d+", str(ticket_id)):
            raise ValueError("Invalid ticket ID")
        return self._shared("TicketHistoryGet", str(ticket_id), lambda: self._get_history(ticket_id))

    def _get_history(self, ticket_id):
        payload = self._request("TicketHistoryGet", str(ticket_id), data=self._auth())
        items = payload.get("TicketHistory")
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list) or len(items) != 1 or str(items[0].get("TicketID")) != str(ticket_id):
            raise ZnunyError("Die Tickethistorie von Znuny ist ungültig.")
        history = items[0].get("History")
        if not isinstance(history, list) or any(not isinstance(item, dict) for item in history):
            raise ZnunyError("Die Tickethistorie von Znuny ist ungültig.")
        return history

    def session_valid(self):
        self._auth()
        self._request("SessionGet", quote(self._session_id, safe=""))
        return True

    def test_connection(self):
        self.search_tickets(limit=1)
        return self.connected
