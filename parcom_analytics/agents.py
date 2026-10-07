"""Verified identities and event-based agent attribution, without owner inference."""

from statistics import median

from .live_metrics import server_datetime
from .analytics import numeric_values

SEED_AGENTS = {
    "1": ("SYSTEM", "SYSTEM", "SYSTEM"),
    "3": ("AndreaDoerig", "Andrea Rafael Dörig", "ADO"),
    "4": ("RafaelPfruender", "Rafael Pfründer", "RPF"),
    "32": ("raphaelschmid", "Raphael Schmid", "RSD"),
    "61": ("nicokoechli", "Nico Köchli", "NKO"),
    "69": ("diogorelvas", "Diogo Mendes Relvas", "DRE"),
    "70": ("larsschmidli", "Lars Schmidli", "LSC"),
    "71": ("rojenkarayapi", "Rojen Karayapi", "RKA"),
    "75": ("lewinroos", "lewinroos", None),
    "76": ("livioriederer", "Livio Riederer", "LRI"),
    "80": ("Krishnamenan", "Krishnamenan Sandirasegaram", "KSA"),
}
KNOWN_STATE_TYPES = {"closed successful":"closed", "closed unsuccessful":"closed",
                     "ohne Rückmeldung geschlossen":"closed", "13":"closed"}
RESPONSE_EVENTS = {"SendAnswer", "PhoneCallAgent", "EmailAgent"}


def identifier(value):
    text = str(value)
    return text if text.isdigit() else None


def code(value):
    agent_id = identifier(value)
    if not agent_id:
        return "Unbekannt"
    known = SEED_AGENTS.get(agent_id)
    return known[2] if known and known[2] else f"ID {agent_id}"


def identity(value, login=None):
    agent_id = identifier(value)
    if not agent_id:
        return None
    known = SEED_AGENTS.get(agent_id)
    return {"id":agent_id, "login":known[0] if known else str(login or ""),
            "name":known[1] if known else str(login or f"ID {agent_id}"), "code":code(agent_id)}


def state_types(tickets):
    result = dict(KNOWN_STATE_TYPES)
    for ticket in tickets:
        kind = str(ticket.get("StateType") or "").lower()
        if kind:
            for key in (ticket.get("State"),ticket.get("StateID")):
                if key is not None:
                    result[str(key)] = kind
    return result


def closed_event(history, start, end, mapping):
    qualifying = []
    for event in history:
        stamp = server_datetime(event.get("CreateTime"))
        if event.get("HistoryType") != "StateUpdate" or not stamp or not start <= stamp < end:
            continue
        parts = [part for part in str(event.get("Name", "")).split("%%") if part]
        target = parts[-1] if parts else ""
        kind = str(event.get("StateType") or mapping.get(str(event.get("StateID"))) or mapping.get(target) or "").lower()
        if kind == "closed":
            qualifying.append((stamp, identifier(event.get("CreateBy"))))
    if not qualifying:
        return None, None
    latest = max(stamp for stamp, _ in qualifying)
    actors = {actor for stamp, actor in qualifying if stamp == latest}
    actor = actors.pop() if len(actors) == 1 else None
    # The actual final close wins; SYSTEM never credits the prior human who armed a timer.
    return actor, latest


def response_actor(ticket, history):
    stamp = server_datetime(ticket.get("FirstResponse"))
    if not stamp:
        return None, None
    matches = [event for event in history if server_datetime(event.get("CreateTime"))
               and abs((server_datetime(event["CreateTime"])-stamp).total_seconds()) <= 5]
    preferred = [event for event in matches if event.get("HistoryType") in RESPONSE_EVENTS]
    candidates = preferred or matches
    actors = {identifier(event.get("CreateBy")) for event in candidates}
    actors.discard("1")
    if len(actors) == 1 and None not in actors:
        return actors.pop(), stamp
    return None, stamp


def metrics(batch, selected):
    import pandas as pd
    opened = batch.frames[3].drop_duplicates("TicketID")
    activity = pd.DataFrame(batch.agents)
    rows = []
    for agent_id in selected:
        owned = opened["OwnerID"].map(str).eq(agent_id)
        current = activity.loc[activity["period"].eq("current")] if not activity.empty else activity
        closed = current.loc[current["ClosedByID"].map(str).eq(agent_id)] if not current.empty else current
        responses = current.loc[current["ResponseByID"].map(str).eq(agent_id)] if not current.empty else current
        times = numeric_values(responses["response_minutes"]).dropna() if not responses.empty else []
        rows.append({"id":agent_id, "Techniker":code(agent_id), "Aktuell im Besitz":int(owned.sum()),
                     "Davon gesperrt":int((owned & opened["Sperre"].eq("Gesperrt")).sum()),
                     "Geschlossen":len(closed), "Erstantworten":len(responses),
                     "Reaktionszeit (Min.)":float(median(times)) if len(times) else None})
    return rows
