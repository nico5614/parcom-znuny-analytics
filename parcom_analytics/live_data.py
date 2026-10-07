"""Normalize read-only REST data into the existing Excel analytics schema."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import calendar
import math
from threading import Event
from zoneinfo import ZoneInfo

import pandas as pd

from .analytics import DataError
from .znuny import DEFAULT_QUEUES, OPEN_TYPES, WAITING_TYPES, SEARCH_LIMIT, ZnunyError

TIMEZONE = "Europe/Zurich"
FIELD_MAP = {"TicketNumber": "Ticket#", "TicketID": "TicketID", "Title": "Titel",
             "Created": "Erstellt", "Changed": "Zuletzt geändert", "Closed": "Schließzeit",
             "Queue": "Queue", "State": "Status", "Priority": "Priorität",
             "FirstResponseInMin": "Erstantwortzeit in Minuten", "SolutionInMin": "Lösungszeit in Minuten",
             "FirstResponseTimeEscalation": "FirstResponseTimeEscalation",
             "FirstResponseTimeDestinationDate": "FirstResponseTimeDestinationDate"}
NORMALIZED_COLUMNS = [*FIELD_MAP.values(), "Alter"]


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


def normalize_tickets(tickets: list[dict]) -> pd.DataFrame:
    rows = []
    for ticket in tickets:
        row = {column: ticket.get(field) for field, column in FIELD_MAP.items()}
        try:
            seconds = float(ticket.get("Age"))
            row["Alter"] = f"{int(seconds // 60)} m" if math.isfinite(seconds) and seconds >= 0 else None
        except (TypeError, ValueError):
            row["Alter"] = None
        rows.append(row)
    # Explicit allowlist: articles, credentials and customer identifiers never enter the model.
    return pd.DataFrame(rows, columns=NORMALIZED_COLUMNS, dtype=object)


def fetch_live(client, period: DateRange, cancel: Event, progress=lambda value: None) -> LiveBatch:
    def search(filters):
        if cancel.is_set():
            raise ZnunyError("Laden abgebrochen.")
        ids = client.search_tickets(filters)
        if len(ids) >= SEARCH_LIMIT:
            raise ZnunyError("Die Suchgrenze wurde erreicht. Bitte einen kleineren Zeitraum wählen; es werden keine unvollständigen Ergebnisse übernommen.")
        return ids

    def dated(field):
        return {f"Ticket{field}TimeNewerDate": f"{period.start} 00:00:00",
                f"Ticket{field}TimeOlderDate": f"{period.end} 23:59:59", "SearchInArchive": "AllTickets"}

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
