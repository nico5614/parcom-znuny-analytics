"""Synthetic, opt-in desktop validation. Never reads or connects to live Znuny."""
from datetime import datetime, timedelta

from ..agents import identity
from ..live_data import LiveBatch, normalize_tickets
from ..periods import TimeRange, ZURICH
from ..znuny import LoginError, ConnectionError
from .dto import TYPES


class ValidationClient:
    def __init__(self):
        self.connected = False
        self._session_id = None

    def login(self, username, password):
        if username == "network-error":
            raise ConnectionError("Synthetischer Netzwerkfehler")
        if username != "validation" or password != "validation":
            raise LoginError("Synthetischer Anmeldefehler")
        self.connected, self._session_id = True, "synthetic-validation-session"

    def logout(self):
        self.connected, self._session_id = False, None

    def search_tickets(self, filters, limit=1):
        return ["1"]


def validation_batch(period=None):
    period = period or TimeRange.preset()
    captured = datetime.now(ZURICH).replace(microsecond=0)
    owners = ["61", "3", "69", "99"]
    titles = ["Synthetisches Ticket · Telefonanlage", "Synthetisches Ticket · Rufumleitung", "Synthetisches Ticket · Teilnehmer konfigurieren", "Synthetisches Ticket · Wartung"]
    def ticket(index, closed=False, waiting=False):
        created = period.start + (period.end - period.start) * ((index % 19 + 1) / 21)
        until = -1800 if index % 3 == 0 else 7200 if index % 3 == 1 else 0
        return {"TicketID": str(index), "TicketNumber": f"TEST{index:05}", "Title": titles[index % 4],
                "Created": created.isoformat(), "Changed": created.isoformat(), "Closed": (created + timedelta(minutes=20)).isoformat(),
                "Queue": "PBX" if index % 4 else "PBX Intern", "State": "closed successful" if closed else "pending reminder" if waiting else "open",
                "StateType": "closed" if closed else "pending reminder" if waiting else "pending auto" if index % 7 == 0 else "open",
                "Type": TYPES[index % len(TYPES)], "Age": (index % 8 + 1) * 7 * 86400, "CustomerID": "00325" if index % 2 else "SYNTHETIC-CUSTOMER",
                "OwnerID": owners[index % 4], "Owner": "test.missing" if owners[index % 4] == "99" else "validation",
                "Lock": "lock" if index % 2 else "unlock", "UntilTime": until if waiting else 0,
                "FirstResponse": created.isoformat(), "FirstResponseInMin": [0, 10, 25, 65][index % 4], "SolutionInMin": [0, 60, 120, 480][index % 4],
                "FirstResponseTimeEscalation": index % 5 == 0, "Aktuell eskaliert": int(index % 5 == 0),
                "ClosedByID": owners[index % 4] if closed else None, "ResponseByID": owners[index % 4] if closed else None,
                "Priority": "3 normal"}
    new = normalize_tickets([ticket(i) for i in range(1, 29)], captured)
    closed = normalize_tickets([ticket(i, closed=True) for i in range(50, 74)], captured)
    opened = normalize_tickets([ticket(i, waiting=i % 3 == 0) for i in range(100, 132)], captured)
    waiting = normalize_tickets([ticket(i, waiting=True) for i in range(102, 120)], captured)
    previous = normalize_tickets([ticket(i, closed=True) for i in range(200, 216)], captured)
    activity = [{"TicketID": row["TicketID"], "Ticket#": row["Ticket#"], "Titel": row["Titel"], "Typ": row["Typ"], "Status": row["Status"],
                 "period": "current", "ClosedByID": row["ClosedByID"], "ResponseByID": row["ResponseByID"],
                 "response_minutes": row["Erstantwortzeit in Minuten"]} for row in closed.to_dict("records")]
    return LiveBatch(period, captured.isoformat(), {1: new, 2: closed, 3: opened, 4: opened.copy(), 5: closed.copy(), 6: closed.copy(), 7: waiting},
                     {1: previous, 2: previous, 5: previous, 6: previous}, activity, "Synthetischer Validierungsdatenstand",
                     [identity(owner, "test.missing" if owner == "99" else None) for owner in owners], captured.isoformat())
