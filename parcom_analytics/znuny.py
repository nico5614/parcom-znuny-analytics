"""Read-only GenericTicketConnectorREST client; credentials never leave memory."""

import logging
import re
from urllib.parse import quote

import truststore

# Use the native Windows trust store so company-managed/intermediate CAs work
# without disabling TLS verification.
truststore.inject_into_ssl()

import requests

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
    def __init__(self, transport=None):
        self._http = transport or requests.Session()
        self._http.trust_env = False
        self._session_id = None
        self.connected = False

    def _request(self, operation, suffix="", data=None, timeout=(5, 30)):
        # Routes are intentionally closed: there is no generic write-ticket API.
        method, path = {"SessionCreate": ("POST", "/Session"),
                        "SessionDelete": ("DELETE", "/Session/" + suffix),
                        "TicketSearch": ("POST", "/Ticket/Search"),
                        "TicketGet": ("GET", "/Ticket/" + suffix)}[operation]
        LOGGER.info("Znuny operation: %s", operation)
        try:
            request_data = {"params": data} if method == "GET" else ({"json": data} if data is not None else {})
            response = self._http.request(method, BASE_URL + path, **request_data,
                                          timeout=timeout, verify=True, allow_redirects=False)
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
        self._session_id = None
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
        session_id, self._session_id = self._session_id, None
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

    def get_tickets(self, ticket_ids):
        ids = [str(value) for value in ticket_ids]
        if not ids or len(ids) > 50 or any(not re.fullmatch(r"\d+", value) for value in ids):
            raise ValueError("Invalid ticket ID")
        tickets = []
        for ticket_id in ids:
            payload = self._request("TicketGet", ticket_id, data={**self._auth(), "Extended": 1,
                                    "AllArticles": 0, "Attachments": 0, "DynamicFields": 0})
            item = payload.get("Ticket")
            if isinstance(item, list):
                item = item[0] if len(item) == 1 else None
            if not isinstance(item, dict) or str(item.get("TicketID")) != ticket_id:
                raise ZnunyError("Die Ticketantwort von Znuny ist ungültig.")
            tickets.append(item)
        return tickets

    def test_connection(self):
        self.search_tickets(limit=1)
        return self.connected
