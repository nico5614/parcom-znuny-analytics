"""Verified identities and event-based agent attribution, without owner inference."""

from statistics import median
import re
import unicodedata

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
    "75": ("lewinroos", "Lewin Roos", "LRO"),
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


def abbreviation(name):
    """First initial and first two surname letters, with consistent transliteration."""
    name = str(name).translate(str.maketrans({"ß": "ss", "ẞ": "SS", "ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE"}))
    plain = "".join(char for char in unicodedata.normalize("NFKD", name) if not unicodedata.combining(char))
    words = [re.sub(r"[^A-Za-z]", "", word) for word in plain.split()]
    words = [word for word in words if word]
    return (words[0][0] + words[-1][:2]).upper() if len(words) >= 2 else None


def resolved_identity(item, override=None):
    item, override = dict(item), override or {}
    item["name"] = override.get("name", item["name"])
    # Existing explicit codes take priority over automatic generation.
    explicit = item.get("code") if not str(item.get("code", "")).startswith("ID ") else None
    item["code"] = override.get("code") or explicit or abbreviation(item["name"]) or f'ID {item["id"]}'
    return item


def discover(batch, registry=None):
    """Keep only humans observed in PBX/PBX Intern, using mappings just for names."""
    from .znuny import DEFAULT_QUEUES
    registry = registry or {}
    observed = {key for key, item in registry.items() if item.get("pbxObserved") and key != "1"}
    logins = {}
    if batch:
        for frame in (*batch.frames.values(), *batch.previous.values()):
            scoped = frame.loc[frame["Queue"].isin(DEFAULT_QUEUES)]
            for row in scoped.to_dict("records"):
                for column in ("OwnerID", "ClosedByID", "ResponseByID"):
                    key = identifier(row.get(column))
                    if key and key != "1":
                        observed.add(key)
                        if column == "OwnerID" and row.get("OwnerLogin"):
                            logins[key] = row["OwnerLogin"]
        for row in batch.agents:
            if row.get("Queue") not in (*DEFAULT_QUEUES, None):
                continue
            for column in ("ClosedByID", "ResponseByID"):
                key = identifier(row.get(column))
                if key and key != "1":
                    observed.add(key)
        observed.update(item["id"] for item in batch.identities if item.get("pbxObserved") and item["id"] != "1")
    mappings = {**registry, **{item["id"]: item for item in batch.identities}} if batch else registry
    result = {}
    for key in observed:
        item = {**identity(key, logins.get(key)), **mappings.get(key, {})}
        item["pbxObserved"] = True
        result[key] = item
    return result


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
    from .znuny import DEFAULT_QUEUES
    from .comparisons import comparison, snapshot_context
    opened = batch.frames[3].loc[batch.frames[3]["Queue"].isin(DEFAULT_QUEUES)].drop_duplicates("TicketID")
    activity = pd.DataFrame(batch.agents)
    if not activity.empty and "Queue" in activity:
        activity = activity.loc[activity["Queue"].isin(DEFAULT_QUEUES) | activity["Queue"].isna()]
    rows = []
    for agent_id in selected:
        if agent_id == "1":
            continue
        owned = opened["OwnerID"].map(str).eq(agent_id)
        current = activity.loc[activity["period"].eq("current")] if not activity.empty else activity
        closed = current.loc[current["ClosedByID"].map(str).eq(agent_id)] if not current.empty else current
        responses = current.loc[current["ResponseByID"].map(str).eq(agent_id)] if not current.empty else current
        times = numeric_values(responses["response_minutes"]).dropna() if not responses.empty else []
        previous = activity.loc[activity["period"].eq("previous") & activity["ResponseByID"].map(str).eq(agent_id)] if not activity.empty else activity
        old_times = numeric_values(previous["response_minutes"]).dropna() if not previous.empty else []
        response_median = float(median(times)) if len(times) else None
        response_mean = float(sum(times) / len(times)) if len(times) else None
        old_median = float(median(old_times)) if len(old_times) else None
        old_mean = float(sum(old_times) / len(old_times)) if len(old_times) else None
        rows.append({"id":agent_id, "Techniker":code(agent_id), "Aktuell im Besitz":int(owned.sum()),
                     "Davon gesperrt":int((owned & opened["Sperre"].eq("Gesperrt")).sum()),
                     "Geschlossen":len(closed), "Erstantworten":len(responses),
                     "Reaktionszeit (Min.)":response_median,
                     "medianResponseMinutes":response_median, "meanResponseMinutes":response_mean,
                     "responseComparison":comparison(response_median, old_median, unit="minutes"),
                     "meanResponseComparison":comparison(response_mean, old_mean, unit="minutes")})
    rows.sort(key=lambda row: (-row["Geschlossen"], row["id"]))
    most = max((row["Geschlossen"] for row in rows), default=0)
    rank, last_count = 0, None
    for index, row in enumerate(rows, 1):
        if row["Geschlossen"] != last_count:
            rank, last_count = index, row["Geschlossen"]
        row["rank"] = rank if batch.history_loaded else None
        row["isPeriodWinner"] = bool(batch.history_loaded and most > 0 and row["Geschlossen"] == most)
        if not snapshot_context(batch)["snapshotIsNow"]:
            row["Aktuell im Besitz"] = row["Davon gesperrt"] = None
        if not batch.history_loaded:
            for key in ("Geschlossen", "Erstantworten", "Reaktionszeit (Min.)", "medianResponseMinutes", "meanResponseMinutes"):
                row[key] = None
            row["responseComparison"] = comparison(None, unit="minutes")
            row["meanResponseComparison"] = comparison(None, unit="minutes")
    return rows
