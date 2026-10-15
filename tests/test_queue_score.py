from dataclasses import replace
from unittest.mock import Mock

from parcom_analytics.live_cache import LiveCache
from parcom_analytics.web.bridge import DesktopBridge
from parcom_analytics.web.settings import Settings
from parcom_analytics.web.validation import validation_batch
from parcom_analytics.znuny import ZnunyClient


def test_queue_search_default_all_and_individual():
    client = ZnunyClient()
    client._session_id = "synthetic"
    client._request = Mock(return_value={"TicketIDs": []})
    client.search_tickets()
    assert client._request.call_args.kwargs["data"]["Queues"] == ["PBX", "PBX Intern"]
    client.queues = None
    client.search_tickets()
    assert "Queues" not in client._request.call_args.kwargs["data"]
    client.queues = ("Video",)
    client.search_tickets()
    assert client._request.call_args.kwargs["data"]["Queues"] == ["Video"]


def test_scope_switch_cache_isolation_and_offline_state(tmp_path):
    cache = LiveCache(tmp_path)
    cache.update(validation_batch())
    client = Mock(connected=True)
    batch = validation_batch()
    for frame in batch.frames.values():
        frame["Queue"] = "Video"
    bridge = DesktopBridge(client=client, cache=cache, settings=Settings(tmp_path), fetch=lambda period: replace(batch, period=period))
    bridge._username = "test"
    assert bridge.refresh({"preset": "1W", "queues": None})["ok"]
    assert cache.batch.queues is None
    assert "Video" in bridge.getState()["availableQueues"]
    assert bridge.getState()["queues"] is None
    restored = LiveCache(tmp_path)
    assert restored.batch.queues is None
    assert not bridge.refresh({"preset": "1W", "queues": []})["ok"]
    # The committed all-queue data survive an invalid selection.
    assert bridge.getState()["queues"] is None
    assert bridge.refresh({"preset": "1W", "queues": ["Video"]})["ok"]
    assert LiveCache(tmp_path).batch.queues == ("Video",)


def test_partial_score_math_missing_values_and_zero_baseline(tmp_path):
    cache = LiveCache(tmp_path)
    batch = validation_batch()
    for kpi, column, before, after in ((5, "Erstantwortzeit in Minuten", 10, 20), (6, "Lösungszeit in Minuten", 40, 20)):
        batch.previous[kpi][column] = before
        batch.frames[kpi][column] = after
    cache.update(batch)
    score = cache.selected_performance()
    assert score["value"] == 75
    assert score["areas"] == {"Reaktionszeit": 50, "Lösungszeit": 100}
    assert "2 von 5" in score["issue"]
    assert cache.management().performance.current.value == 75
    batch.previous[5]["Erstantwortzeit in Minuten"] = 0
    batch.frames[6]["Lösungszeit in Minuten"] = None
    cache.update(batch)
    assert cache.selected_performance()["value"] == 1
    assert "1 von 5" in cache.selected_performance()["issue"]
    batch.frames[5]["Erstantwortzeit in Minuten"] = None
    cache.update(batch)
    assert cache.selected_performance()["value"] is None


def test_all_queue_fetch_accepts_non_pbx_ticket_and_agents():
    from threading import Event
    from parcom_analytics.live_data import fetch_live
    from parcom_analytics.periods import TimeRange
    from parcom_analytics.agents import metrics
    client = Mock(queues=None)
    client.search_tickets.side_effect = [[], [], ["9"], [], [], [], []]
    client.get_tickets.return_value = [{"TicketID": "9", "TicketNumber": "9", "Title": "Synthetic", "Queue": "Video", "Age": 0, "State": "open", "StateType": "open", "OwnerID": "17", "Lock": "unlock"}]
    batch = fetch_live(client, TimeRange.preset(), Event())
    assert batch.queues is None
    assert batch.frames[3]["Queue"].tolist() == ["Video"]
    assert metrics(batch, ["17"])[0]["Aktuell im Besitz"] == 1


def test_closed_event_counts_are_not_removed_by_current_reopened_state():
    from datetime import datetime
    from threading import Event
    from parcom_analytics.live_data import fetch_live
    from parcom_analytics.periods import TimeRange, ZURICH
    client = Mock(queues=None)
    client.search_tickets.side_effect = [[], ["9"], ["9"], [], [], [], []]
    client.get_tickets.return_value = [{"TicketID": "9", "TicketNumber": "9", "Title": "Synthetic", "Queue": "Video", "Age": 0, "State": "open", "StateType": "open", "Closed": "2026-10-13 10:00:00", "FirstResponseInMin": 10, "SolutionInMin": 20}]
    batch = fetch_live(client, TimeRange.preset("1W", datetime(2026, 10, 14, 12, tzinfo=ZURICH)), Event())
    assert len(batch.frames[2]) == 1
    assert "StateType" not in client.search_tickets.call_args_list[1].args[0]
