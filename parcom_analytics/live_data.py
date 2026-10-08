"""Normalize read-only REST data into the existing Excel analytics schema."""

from dataclasses import dataclass, field
from copy import deepcopy
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import calendar
import math
from threading import Event
from zoneinfo import ZoneInfo

import pandas as pd

from .analytics import DataError
from .znuny import DEFAULT_QUEUES, OPEN_TYPES, WAITING_TYPES, SEARCH_LIMIT, ZnunyClient, ZnunyError
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
    identities: list[dict] = field(default_factory=list)
    load_started_at: str = ""
    history_loaded: bool = True
    # Memory-only staging. Never serialize raw REST responses or history.
    _state: object = field(default=None, repr=False, compare=False)


@dataclass
class TicketState:
    tickets: dict = field(default_factory=dict)
    selections: dict = field(default_factory=dict)
    synced_at: str = ""
    generation: int = 0
    period: object = None


def commit_live(client, batch):
    """Publish the sync watermark only after analytics and disk persistence succeed."""
    if isinstance(client, ZnunyClient) and batch._state is not None:
        with client._lock:
            if batch._state.generation != client._generation:
                raise ZnunyError("Die Znuny-Sitzung hat sich geändert. Bitte erneut laden.")
            client._live_state = batch._state


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
        row["Timer"], row["Warten bis"] = timer(ticket.get("UntilTime"), captured or ticket.get("_captured") or datetime.now(ZURICH))
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


def fetch_live(client, period: DateRange, cancel: Event, progress=lambda value: None, *, commit=True) -> LiveBatch:
    context = client.timings.measure("DashboardLoad") if isinstance(client, ZnunyClient) else nullcontext()
    lock = client._refresh_lock if isinstance(client, ZnunyClient) else nullcontext()
    with lock, context:
        batch = _fetch_live(client, period, cancel, progress)
        if cancel.is_set():
            raise ZnunyError("Laden abgebrochen.")
        if commit:
            commit_live(client, batch)
        return batch


def _fetch_live(client, period, cancel, progress):
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
    started_at = datetime.now(ZURICH).isoformat(timespec="seconds")
    generation = client._generation if isinstance(client, ZnunyClient) else 0
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
    old = client._live_state if isinstance(client, ZnunyClient) else None
    changed = set(search({"TicketLastChangeTimeNewerDate":
        (datetime.fromisoformat(old.synced_at).astimezone(timezone.utc)-timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S"),
        "SearchInArchive": "AllTickets"})) if old else set()
    needed = [value for value in ids if old is None or value not in old.tickets or value in changed]
    required = set(needed)
    tickets = {value: deepcopy(old.tickets[value]) for value in ids if value not in required} if old else {}
    if isinstance(client, ZnunyClient):
        client.invalidate_history(changed)
    for offset in range(0, len(needed), 50):
        if cancel.is_set():
            raise ZnunyError("Laden abgebrochen.")
        for ticket in client.get_tickets(needed[offset:offset+50], cancel=cancel):
            if ticket.get("Queue") not in DEFAULT_QUEUES:
                raise ZnunyError("Die Daten haben sich während des Ladens geändert. Bitte erneut aktualisieren.")
            # Cache only the fields the application consumes, never articles/auth.
            safe = {key: deepcopy(value) for key, value in ticket.items()
                    if key in {*FIELD_MAP, "Age", "CustomerID"}}
            safe["_captured"] = datetime.now(ZURICH)
            tickets[str(ticket["TicketID"])] = safe
        progress(round(min(offset+50, len(needed))/max(1,len(needed))*100))
    if any(value not in tickets for value in ids):
        raise ZnunyError("Znuny lieferte einen unvollständigen Datenstand.")
    raw_tickets = deepcopy(tickets)
    if old and old.period == period:
        raw_tickets.update({key: deepcopy(value) for key, value in old.tickets.items()
                            if key not in raw_tickets and key not in changed})
    escalated = set(selections["escalated"])
    for ticket_id, ticket in tickets.items():
        age_ticket(ticket)
        ticket["Aktuell eskaliert"] = int(ticket_id in escalated)
        # Only an absent pending timer requires history for normal dashboard KPIs.
        if ticket.get("UntilTime") is None and str(ticket.get("StateType", "")).startswith("pending"):
            history = ticket_history(client, ticket, cancel)
            pending_timer(ticket, history)

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
            rows.append(ticket)
        return normalize_tickets(rows)

    new, closed, opened, waiting = (frame(key) for key in ("new", "closed", "open", "waiting"))
    old_new, old_closed = frame("previous_new"), frame("previous_closed")
    return LiveBatch(period, datetime.now(ZURICH).isoformat(timespec="seconds"),
                     {1:new, 2:closed, 3:opened, 4:opened.copy(), 5:closed.copy(), 6:closed.copy(), 7:waiting},
                     {1:old_new, 2:old_closed, 5:old_closed.copy(), 6:old_closed.copy()},
                     load_started_at=started_at, history_loaded=False,
                     _state=TicketState(raw_tickets, selections, started_at,
                                        generation, period))


def age_ticket(ticket):
    """Advance relative REST values without pretending the ticket changed."""
    now = datetime.now(ZURICH)
    elapsed = max(0, (now-ticket["_captured"]).total_seconds())
    for name, direction in (("Age", 1), ("UntilTime", -1)):
        try:
            value = float(ticket.get(name))
            if math.isfinite(value) and (name != "UntilTime" or value != 0):
                ticket[name] = value + direction*elapsed
        except (ValueError, TypeError):
            pass
    ticket["_captured"] = now


def ticket_history(client, ticket, cancel):
    if cancel.is_set():
        raise ZnunyError("Laden abgebrochen.")
    if isinstance(client, ZnunyClient):
        return client.get_history(ticket["TicketID"], changed=ticket.get("Changed"), cancel=cancel)
    return client.get_history(ticket["TicketID"])


def pending_timer(ticket, history):
    if ticket.get("UntilTime") is None and str(ticket.get("StateType", "")).startswith("pending"):
        from .live_metrics import server_datetime
        pending = [event for event in history if event.get("HistoryType") == "SetPendingTime" and server_datetime(event.get("CreateTime"))]
        if pending:
            latest = max(pending, key=lambda item:server_datetime(item["CreateTime"]))
            value = str(latest.get("Name", "")).strip("%")
            due = server_datetime(value)
            if due:
                ticket["UntilTime"] = due.timestamp()-ticket["_captured"].timestamp()
            elif value.startswith("0000-00-00") or value.startswith("00-00-00"):
                ticket["UntilTime"] = 0


def attribute_history(client, tickets, period, cancel):
    from .agents import state_types, identity, closed_event, response_actor
    previous_start, previous_end = period.previous
    mapping, activity, identities = state_types(tickets.values()), [], {}
    def fetch(ticket):
        return ticket_history(client, ticket, cancel)
    if isinstance(client, ZnunyClient):
        with ThreadPoolExecutor(max_workers=client.concurrency, thread_name_prefix="znuny-history") as pool:
            histories = list(pool.map(fetch, tickets.values(), buffersize=client.concurrency))
    else:
        histories = [fetch(ticket) for ticket in tickets.values()]
    for (ticket_id, ticket), history in zip(tickets.items(), histories):
        if cancel.is_set():
            raise ZnunyError("Laden abgebrochen.")
        if not isinstance(history, list):
            raise ZnunyError("Die Tickethistorie von Znuny ist ungültig.")
        owner = identity(ticket.get("OwnerID"), ticket.get("Owner"))
        if owner:
            identities[owner["id"]] = owner
        for event in history:
            actor = identity(event.get("CreateBy"))
            if actor and actor["id"] not in identities:
                identities[actor["id"]] = actor
        responder, response_time = response_actor(ticket, history)
        for key, start, end in (("current", period.start, period.end), ("previous", previous_start, previous_end)):
            closer, closed_time = closed_event(history, start, end, mapping)
            response_in_period = response_time is not None and start <= response_time < end
            if key == "current":
                ticket.update({"ClosedByID":closer, "ClosedAt":closed_time.isoformat() if closed_time else None,
                               "ResponseByID":responder if response_in_period else None,
                               "ResponseAt":response_time.isoformat() if response_in_period else None})
            if closed_time or response_in_period:
                activity.append({"TicketID":ticket_id, "Ticket#":ticket.get("TicketNumber"), "Titel":ticket.get("Title"),
                                 "Typ":ticket.get("Type"), "Status":ticket.get("State"), "period":key,
                                 "ClosedByID":closer, "ResponseByID":responder if response_in_period else None,
                                 "ClosedAt":closed_time.isoformat() if closed_time else None,
                                 "ResponseAt":response_time.isoformat() if response_in_period else None,
                                 "response_minutes":ticket.get("FirstResponseInMin") if response_in_period else None})

    return activity, list(identities.values())


def load_history(client, batch, cancel, progress=lambda value: None):
    """Build agent activity on demand without mutating the displayed snapshot."""
    if batch.history_loaded or batch._state is None:
        return batch
    if cancel.is_set():
        raise ZnunyError("Laden abgebrochen.")
    if isinstance(client, ZnunyClient) and batch._state.generation != client._generation:
        raise ZnunyError("Die Znuny-Sitzung hat sich geändert. Bitte erneut laden.")
    from dataclasses import replace
    state = deepcopy(batch._state)
    tickets = state.tickets
    previous_start, _ = batch.period.previous
    ids = client.search_tickets({"TicketLastChangeTimeNewerDate":
        previous_start.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "SearchInArchive": "AllTickets"})
    if len(ids) >= SEARCH_LIMIT:
        raise ZnunyError("Die Suchgrenze wurde erreicht. Bitte einen kleineren Zeitraum wählen.")
    selected = {value for values in state.selections.values() for value in values} | set(ids)
    tickets = {key: value for key, value in tickets.items() if key in selected}
    state.tickets = tickets
    missing = [value for value in ids if value not in tickets]
    for offset in range(0, len(missing), 50):
        for ticket in client.get_tickets(missing[offset:offset+50], cancel=cancel):
            if ticket.get("Queue") not in DEFAULT_QUEUES:
                raise ZnunyError("Die Daten haben sich während des Ladens geändert. Bitte erneut aktualisieren.")
            safe = {key: deepcopy(value) for key, value in ticket.items()
                    if key in {*FIELD_MAP, "Age", "CustomerID"}}
            safe["_captured"] = datetime.now(ZURICH)
            tickets[str(ticket["TicketID"])] = safe
    if any(value not in tickets for value in ids):
        raise ZnunyError("Znuny lieferte einen unvollständigen Datenstand.")
    activity, identities = attribute_history(client, tickets, batch.period, cancel)
    if cancel.is_set():
        raise ZnunyError("Laden abgebrochen.")
    frames = {key: frame.copy(deep=True) for key, frame in batch.frames.items()}
    for frame in frames.values():
        for column in ("ClosedByID", "ClosedAt", "ResponseByID", "ResponseAt"):
            frame[column] = frame["TicketID"].map(lambda value: tickets[str(value)].get(column))
    # Retain only unannotated raw fields in the transactional ticket cache.
    for ticket in tickets.values():
        for column in ("ClosedByID", "ClosedAt", "ResponseByID", "ResponseAt"):
            ticket.pop(column, None)
    progress(100)
    return replace(batch, frames=frames, agents=activity, identities=identities,
                   history_loaded=True, _state=state)
