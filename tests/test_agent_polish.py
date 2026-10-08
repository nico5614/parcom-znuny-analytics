from dataclasses import replace
from datetime import timedelta

import pytest

from parcom_analytics import agents
from parcom_analytics.live_cache import LiveCache
from parcom_analytics.web.bridge import DesktopBridge
from parcom_analytics.web.dto import agents_dto, identities, overview
from parcom_analytics.web.settings import Settings
from parcom_analytics.web.validation import validation_batch


@pytest.fixture
def data(tmp_path):
    cache = LiveCache(tmp_path)
    batch = validation_batch()
    batch.frames[3].loc[0, ["OwnerID", "OwnerLogin"]] = ["75", "lewinroos"]
    batch.agents = [
        {"TicketID": str(i), "Ticket#": str(i), "period": period, "Queue": queue,
         "ClosedByID": closer, "ResponseByID": responder, "response_minutes": minutes}
        for i, period, queue, closer, responder, minutes in [
            (1, "current", "PBX", "61", "61", 0),
            (2, "current", "PBX Intern", "61", "61", 10),
            (3, "current", "PBX", "75", "75", 1000),
            (4, "previous", "PBX", "61", "61", 20),
            (5, "current", "Other", "75", "61", 8000),
            (6, "current", "PBX", "1", "1", 5),
            (7, "current", "PBX", "1", None, None),
            (8, "current", "PBX", "1", None, None),
        ]]
    cache.update(batch)
    settings = Settings(tmp_path)
    return cache, settings


@pytest.mark.parametrize("name,code", [("Nico Köchli", "NKO"), ("Lewin Roos", "LRO"), ("Andrea Dörig", "ADO"), ("Émilie Müller", "EMU"), ("Åke Øster", "AOS"), ("Nico Koe\u0308chli", "NKO"), ("Jane Smith-Jones", "JSM")])
def test_abbreviation_transliterates_names(name, code):
    assert agents.abbreviation(name) == code


def test_no_name_guess_from_single_login_manual_codes_preserved():
    assert agents.abbreviation("lewinroos") is None
    assert agents.code(75) == "LRO" and agents.identity(75)["name"] == "Lewin Roos"
    item = {"id": "42", "login": "example", "name": "Nico Köchli", "code": "MAN"}
    assert agents.resolved_identity(item)["code"] == "MAN"
    item["code"] = "ID 42"
    assert agents.resolved_identity(item)["code"] == "NKO"
    assert agents.resolved_identity(item, {"code": "USER"})["code"] == "USER"


def test_discover_only_observed_pbx_humans_and_keep_saved_scope(data):
    cache, settings = data
    settings.set({"agent_registry": {"80": agents.identity(80), "88": {**agents.identity(88, "past.login"), "pbxObserved": True}}})
    cache.batch.identities.append(agents.identity(4))
    other = cache.batch.frames[3].iloc[0].copy()
    other["Queue"], other["OwnerID"] = "Unrelated", "123"
    import pandas as pd
    cache.batch.frames[3] = pd.concat([cache.batch.frames[3], other.to_frame().T], ignore_index=True)
    registry = identities(cache, settings)
    assert {"61", "75", "88", "99"}.issubset(registry)
    assert {"1", "80", "4", "123"}.isdisjoint(registry)
    assert registry["75"]["code"] == "LRO"


def test_human_winner_ranking_response_mean_delta_and_team_independence(data):
    cache, settings = data
    settings.set({"team_selection": ["75"]})
    dto = agents_dto(cache, settings)
    assert dto["periodWinner"]["id"] == "61"
    winner = dto["periodWinner"]
    assert winner["Geschlossen"] == 2 and winner["rank"] == 1 and winner["isPeriodWinner"]
    assert winner["medianResponseMinutes"] == 5 and winner["meanResponseMinutes"] == 5
    assert winner["responseComparison"]["delta"] == -15
    assert winner["responseComparison"]["trend"] == "improvement"
    assert dto["rows"][0]["id"] == "75" and not dto["rows"][0]["isPeriodWinner"]
    assert dto["rows"][0]["rank"] == 2 and dto["rows"][0]["Geschlossen"] == 1
    assert overview(cache, settings)["periodWinner"]["id"] == "61"


def test_winner_never_uses_owner_or_system(data):
    cache, settings = data
    for event in cache.batch.agents:
        event["ClosedByID"] = "1"
    cache.batch.frames[3]["OwnerID"] = "61"
    dto = agents_dto(cache, settings)
    assert dto["periodWinners"] == [] and dto["periodWinner"] is None
    assert "1" not in [row["id"] for row in dto["rows"]]


def test_tied_winners_are_explicit_and_unknown_history_has_no_winner(data):
    cache, settings = data
    cache.batch.agents.append({**cache.batch.agents[2], "TicketID": "9"})
    dto = agents_dto(cache, settings)
    assert {row["id"] for row in dto["periodWinners"]} == {"61", "75"}
    assert dto["periodWinner"] is None
    assert all(row["rank"] == 1 for row in dto["periodWinners"])
    cache.batch = replace(cache.batch, history_loaded=False)
    dto = agents_dto(cache, settings)
    assert not dto["winnerAvailable"] and dto["periodWinners"] == []
    assert all(row["Geschlossen"] is None and row["rank"] is None for row in dto["rows"])


def test_local_override_methods_persist_reset_and_use_stable_identity(data, tmp_path):
    cache, settings = data
    bridge = DesktopBridge(root=tmp_path, cache=cache, settings=settings)
    assert not bridge.setAgentDisplayName("61", "Nico")["ok"]
    assert bridge.continueOffline()["ok"]
    assert bridge.setAgentDisplayName("nicokoechli", "Nico Example")["ok"]
    assert bridge.setAgentAbbreviation("61", "ABC")["ok"]
    assert bridge.getAgentOverride("61")["data"] == {"name": "Nico Example", "code": "ABC"}
    registry = identities(cache, settings)
    assert registry["61"]["name"] == "Nico Example" and registry["61"]["code"] == "ABC"
    restarted = DesktopBridge(root=tmp_path)
    assert restarted.continueOffline()["ok"]
    assert restarted.getAgentOverride("nicokoechli")["data"]["code"] == "ABC"
    assert restarted.resetAgentOverride("61")["data"]["code"] == "NKO"
    assert restarted.getAgentOverride("61")["data"] == {}
    assert not restarted.setAgentAbbreviation("1", "SYS")["ok"]
    assert not restarted.setAgentDisplayName("80", "Unrelated")["ok"]
    assert not restarted.setAgentAbbreviation("61", " ")["ok"]
    text = settings._path.read_text(encoding="utf-8")
    assert "Password" not in text and "SessionID" not in text


def test_rename_unknown_agent_derives_abbreviation_without_overwriting_manual(data):
    cache, settings = data
    settings.set({"agent_overrides": {"99": {"name": "Émilie Müller"}}})
    assert identities(cache, settings)["99"]["code"] == "EMU"
    settings.set({"agent_overrides": {"99": {"name": "Other Person", "code": "CUS"}}})
    assert identities(cache, settings)["99"]["code"] == "CUS"


def test_agent_counts_are_unique_tickets_and_median_handles_long_tail(data):
    cache, settings = data
    cache.batch.agents.extend([
        dict(cache.batch.agents[0]),
        {**cache.batch.agents[0], "TicketID": "900", "ClosedByID": None, "response_minutes": 1000}])
    winner = agents_dto(cache, settings)["periodWinner"]
    assert winner["Geschlossen"] == 2 and winner["Erstantworten"] == 3
    assert winner["medianResponseMinutes"] == 10
    assert winner["meanResponseMinutes"] == pytest.approx(1010 / 3)
