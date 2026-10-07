"""Normalize read-only REST data into the existing Excel analytics schema."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import calendar
import math
from threading import Event
from zoneinfo import ZoneInfo

import pandas as pd

from .analytics import DataError
from .znuny import DEFAULT_QUEUES, OPEN_TYPES, WAITING_TYPES, SEARCH_LIMIT, ZnunyError
from .periods import TimeRange, ZURICH

TIMEZONE = "Europe/Zurich"
FIELD_MAP = {"TicketNumber": "Ticket#", "TicketID": "TicketID", "Title": "Titel",
             "Created": "Erstellt", "Changed": "Zuletzt geändert", "Closed": "Schließzeit",
             "Queue": "Queue", "State": "Status", "Priority": "Priorität",
             "FirstResponseInMin": "Erstantwortzeit in Minuten", "SolutionInMin": "Lösungszeit in Minuten",
             "FirstResponseTimeEscalation": "FirstResponseTimeEscalation",
             "FirstResponseTimeDestinationDate": "FirstResponseTimeDestinationDate"}
FIELD_MAP.update({"Type": "Typ", "TypeID": "TypeID", "StateType": "StateType", "StateID": "StateID",
                  "OwnerID": "OwnerID", "Owner": "OwnerLogin", "Lock": "Lock", "LockID": "LockID",
                  "UntilTime": "UntilTime", "FirstResponse": "FirstResponse",
                  "FirstResponseDiffInMin": "FirstResponseDiffInMin", "SolutionDiffInMin": "SolutionDiffInMin",
                  "SolutionTimeEscalation": "SolutionTimeEscalation"})
NORMALIZED_COLUMNS = [*FIELD_MAP.values(), "Alter", "Kundennummer", "Timer", "Warten bis", "Sperre",
                      "Aktuell eskaliert", "ClosedByID", "ResponseByID", "ResponseAt", "ClosedAt"]


def months_before(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 - months
    year, month = divmod(index, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date

    def __post_init__(self):
        if self.end < self.start:
            raise DataError("Das Von-Datum muss vor dem Bis-Datum liegen.")
        if self.start < months_before(self.end + timedelta(days=1), 12):
            raise DataError("Bitte wählen Sie einen Zeitraum von höchstens 12 Monaten.")
        if self.end > datetime.now(ZoneInfo(TIMEZONE)).date():
            raise DataError("Das Bis-Datum darf nicht in der Zukunft liegen.")

    @property
    def label(self):
        return f"{self.start:%d.%m.%Y} – {self.end:%d.%m.%Y}"

    @classmethod
    def preset(cls, value: str, today=None):
        end = today or datetime.now(ZoneInfo(TIMEZONE)).date()
        start = end - timedelta(days=int(value[:-1])-1) if value.endswith("d") else months_before(end + timedelta(days=1), int(value[:-1]))
        return cls(start, end)


@dataclass
class LiveBatch:
    period: DateRange
    captured_at: str
    frames: dict[int, pd.DataFrame]
    previous: dict[int, pd.DataFrame] = field(default_factory=dict)
    agents: list[dict] = field(default_factory=list)
    note: str = ""


def normalize_tickets(tickets: list[dict], captured=None) -> pd.DataFrame:
    rows = []
    for ticket in tickets:
        row = {column: ticket.get(field) for field, column in FIELD_MAP.items()}
        try:
            seconds = float(ticket.get("Age"))
            row["Alter"] = f"{int(seconds // 60)} m" if math.isfinite(seconds) and seconds >= 0 else None
        except (TypeError, ValueError):
            row["Alter"] = None
        row["Kundennummer"] = (str(ticket["CustomerID"]) if ticket.get("CustomerID") not in (None, "", "00325")
                                else "Kein Kunde zugewiesen")
        row["Sperre"] = "Gesperrt" if str(ticket.get("Lock", "")).lower() == "lock" or str(ticket.get("LockID")) == "2" else "Frei" if str(ticket.get("Lock", "")).lower() == "unlock" or str(ticket.get("LockID")) == "1" else "Unbekannt"
        if row["Status"] == "pending reminder":
            row["Status"] = "Warten zur Erinnerung"
        row["Timer"], row["Warten bis"] = timer(ticket.get("UntilTime"), captured or datetime.now(ZURICH))
        for name in ("Aktuell eskaliert", "ClosedByID", "ResponseByID", "ResponseAt", "ClosedAt"):
            row[name] = ticket.get(name)
        rows.append(row)
    # Explicit allowlist: no articles, customer-user logins, credentials or session tokens.
    return pd.DataFrame(rows, columns=NORMALIZED_COLUMNS, dtype=object)


def timer(value, captured):
    # Znuny UntilTime is signed seconds remaining, not an epoch timestamp.
    try:
        seconds = float(value)
        if not math.isfinite(seconds):
            raise ValueError()
    except (ValueError, TypeError):
        return "Unbekannt", None
    if seconds == 0:
        return "Kein Timer", None
    due = datetime.fromtimestamp(captured.timestamp() + seconds, ZURICH)
    return ("Überfällig" if seconds < 0 else "Aktiv"), due.isoformat(timespec="seconds")


def fetch_live(client, period: DateRange, cancel: Event, progress=lambda value: None) -> LiveBatch:
    if isinstance(period, TimeRange):
        return fetch_period(client, period, cancel, progress)
    def search(filters):
        if cancel.is_set():
            raise ZnunyError("Laden abgebrochen.")
        ids = client.search_tickets(filters)
        if len(ids) >= SEARCH_LIMIT:
            raise ZnunyError("Die Suchgrenze wurde erreicht. Bitte einen kleineren Zeitraum wählen; es werden keine unvollständigen Ergebnisse übernommen.")
        return ids

    def dated(field):
        return {f"Ticket{field}TimeNewerDate": period.start.strftime("%Y-%m-%d %H:%M:%S") if isinstance(period.start, datetime) else f"{period.start} 00:00:00",
                f"Ticket{field}TimeOlderDate": period.end.strftime("%Y-%m-%d %H:%M:%S") if isinstance(period.end, datetime) else f"{period.end} 23:59:59", "SearchInArchive": "AllTickets"}

    new_ids = search(dated("Create"))
    closed_ids = search({**dated("Close"), "StateType": "Closed"})
    open_ids = search({"StateType": list(OPEN_TYPES)})
    waiting_ids = search({"StateType": list(WAITING_TYPES)})
    all_ids = list(dict.fromkeys([*new_ids, *closed_ids, *open_ids, *waiting_ids]))
    tickets = {}
    for start in range(0, len(all_ids), 50):
        if cancel.is_set():
            raise ZnunyError("Laden abgebrochen.")
        for ticket in client.get_tickets(all_ids[start:start+50]):
            if ticket.get("Queue") not in DEFAULT_QUEUES:
                raise ZnunyError("Die Daten haben sich während des Ladens geändert. Bitte erneut aktualisieren.")
            tickets[str(ticket["TicketID"])] = ticket
        progress(round(min(start+50, len(all_ids)) / max(1, len(all_ids)) * 100))
    frame = lambda ids: normalize_tickets([tickets[ticket_id] for ticket_id in ids])
    new, closed, opened, waiting = frame(new_ids), frame(closed_ids), frame(open_ids), frame(waiting_ids)
    captured = datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    return LiveBatch(period, captured, {1: new, 2: closed, 3: opened, 4: opened.copy(),
                                       5: closed.copy(), 6: closed.copy(), 7: waiting})


def fetch_period(client, period, cancel, progress):
    def search(filters):
        if cancel.is_set():
            raise ZnunyError("Laden abgebrochen.")
        result = client.search_tickets(filters)
        if len(result) >= SEARCH_LIMIT:
            raise ZnunyError("Die Suchgrenze wurde erreicht. Bitte einen kleineren Zeitraum wählen.")
        return result

    def dated(name, start, end):
        return {f"Ticket{name}TimeNewerDate": start.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                f"Ticket{name}TimeOlderDate": end.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "SearchInArchive": "AllTickets"}

    previous_start, previous_end = period.previous
    selections = {
        "new": search(dated("Create", period.start, period.end)),
        "closed": search({**dated("Close", period.start, period.end), "StateType": "closed"}),
        "open": search({"StateType": list(OPEN_TYPES)}),
        "waiting": search({"StateType": "pending reminder"}),
        "escalated": search({"StateType": list(OPEN_TYPES), "TicketEscalationTimeOlderMinutes": 1}),
        "previous_new": search(dated("Create", previous_start, previous_end)),
        "previous_closed": search({**dated("Close", previous_start, previous_end), "StateType": "closed"}),
    }
    ids = list(dict.fromkeys(value for values in selections.values() for value in values))
    tickets = {}
    escalated = set(selections["escalated"])
    for offset in range(0, len(ids), 50):
        if cancel.is_set():
            raise ZnunyError("Laden abgebrochen.")
        for ticket in client.get_tickets(ids[offset:offset+50]):
            if ticket.get("Queue") not in DEFAULT_QUEUES:
                raise ZnunyError("Die Daten haben sich während des Ladens geändert. Bitte erneut aktualisieren.")
            ticket_id = str(ticket["TicketID"])
            ticket["Aktuell eskaliert"] = int(ticket_id in escalated)
            ticket["_captured"] = datetime.now(ZURICH)
            tickets[ticket_id] = ticket
        progress(round(min(offset+50, len(ids))/max(1,len(ids))*100))

    def frame(key):
        rows = []
        for ticket_id in selections[key]:
            if ticket_id not in tickets:
                raise ZnunyError("Znuny lieferte einen unvollständigen Datenstand.")
            ticket = tickets[ticket_id]
            # The state type, never a substring of a localized state name, controls classification.
            state_type = str(ticket.get("StateType") or "").lower()
            if key.endswith("closed") and state_type and state_type != "closed":
                continue
            if key == "waiting" and state_type and state_type != "pending reminder":
                continue
            if key == "open" and state_type and state_type not in OPEN_TYPES:
                continue
            if key in {"new", "closed", "previous_new", "previous_closed"}:
                from .live_metrics import server_datetime
                stamp = server_datetime(ticket.get("Created" if key.endswith("new") else "Closed"))
                start, end = (previous_start, previous_end) if key.startswith("previous") else (period.start, period.end)
                if stamp is None:
                    raise ZnunyError("Znuny liefert Tickets ohne gültiges Erstellungs- oder Schliessdatum.")
                if not start <= stamp < end:
                    continue
            rows.append(normalize_tickets([ticket], ticket["_captured"]))
        return pd.concat(rows, ignore_index=True) if rows else normalize_tickets([])

    new, closed, opened, waiting = (frame(key) for key in ("new", "closed", "open", "waiting"))
    old_new, old_closed = frame("previous_new"), frame("previous_closed")
    return LiveBatch(period, datetime.now(ZURICH).isoformat(timespec="seconds"),
                     {1:new, 2:closed, 3:opened, 4:opened.copy(), 5:closed.copy(), 6:closed.copy(), 7:waiting},
                     {1:old_new, 2:old_closed, 5:old_closed.copy(), 6:old_closed.copy()})
