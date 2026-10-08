from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest
import requests

from parcom_analytics.connection import ConnectionController, NetworkWorker
from parcom_analytics.live_cache import LiveCache
from parcom_analytics.live_data import fetch_live, load_history, commit_live, age_ticket
from parcom_analytics.live_metrics import analyze_live
from parcom_analytics.periods import TimeRange, ZURICH
from parcom_analytics.znuny import ZnunyClient, ZnunyError, SessionExpired, ConnectionError
from performance_benchmark import BenchmarkTransport, Response
from test_connection import finish


@pytest.fixture
def source():
    transport = BenchmarkTransport(count=8, latency=0)
    client = ZnunyClient(transport)
    client._session_id = "synthetic-session"
    period = TimeRange.preset("1W", datetime(2026, 10, 6, 14, tzinfo=ZURICH))
    return client, transport, period


def counts(transport):
    return {key: item["count"] for key, item in transport.calls.items()}


@pytest.fixture
def jobs(qapp):
    # Keep synchronous QThread wrappers owned by the GUI application until
    # explicitly disposed there; a pool thread must never collect their cycles.
    from PySide6.QtCore import QCoreApplication, QEvent
    workers = []

    def create(*args, **kwargs):
        worker = NetworkWorker(*args, parent=qapp, **kwargs)
        workers.append(worker)
        return worker

    yield create
    for worker in workers:
        worker.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_initial_dashboard_is_lazy_and_delta_reuses_real_tickets(source):
    client, transport, period = source
    first = fetch_live(client, period, Event())
    assert counts(transport) == {"TicketSearch": 7, "TicketGet": 8}
    assert not first.history_loaded and first.agents == []
    transport.reset()
    second = fetch_live(client, period, Event())
    assert counts(transport) == {"TicketSearch": 8}
    for key in first.frames:
        assert analyze_live(key, first.frames[key], period).metrics == analyze_live(key, second.frames[key], period).metrics
    # Caller annotations must never modify the raw cache.
    second.frames[1].loc[0, "Typ"] = "caller mutation"
    assert client._live_state.tickets["1"]["Type"] == "Unclassified"


def test_delta_fetches_only_four_changes_and_refreshes_content(source):
    client, transport, period = source
    fetch_live(client, period, Event())
    transport.reset()
    transport.changed = ["1", "2", "3", "4"]
    original = transport.request

    def changed(method, url, **kwargs):
        response = original(method, url, **kwargs)
        if "/Ticket/" in url and "/History/" not in url and not url.endswith("Search"):
            response.payload["Ticket"][0].update(Changed="2026-10-02 08:00:00", Type="Actual type", TypeID=9)
        return response

    transport.request = changed
    batch = fetch_live(client, period, Event())
    assert counts(transport) == {"TicketSearch": 8, "TicketGet": 4}
    assert batch.frames[3]["Typ"].tolist() == ["Actual type"]*4 + ["Unclassified"]*4
    assert batch.frames[3]["Erstantwortzeit in Minuten"].tolist() == [0]*8


def test_reconciles_queue_removal_even_without_delta_hit(source):
    client, transport, period = source
    fetch_live(client, period, Event())
    original = transport.request

    def removed(method, url, **kwargs):
        response = original(method, url, **kwargs)
        if url.endswith("Search"):
            response.payload["TicketIDs"] = [value for value in response.payload["TicketIDs"] if value != "1"]
        return response

    transport.request = removed
    transport.reset()
    batch = fetch_live(client, period, Event())
    assert "1" not in batch.frames[3]["TicketID"].tolist()
    assert counts(transport) == {"TicketSearch": 8}


def test_period_change_fetches_only_missing_ids(source):
    client, transport, period = source
    fetch_live(client, period, Event())
    transport.count = 9
    transport.reset()
    batch = fetch_live(client, TimeRange(period.start-timedelta(days=1), period.end), Event())
    assert counts(transport) == {"TicketSearch": 8, "TicketGet": 1}
    assert len(batch.frames[3]) == 9


@pytest.mark.parametrize("stage", ["search", "ticket", "disk", "analytics"])
def test_failed_refresh_keeps_cache_and_sync_watermark(jobs, tmp_path, monkeypatch, source, stage):
    client, transport, period = source
    cache = LiveCache(tmp_path)
    worker = jobs(client, "refresh", period, cache=cache)
    worker.run()
    before, state = cache.path.read_bytes(), client._live_state
    original = transport.request
    transport.changed = ["1"]

    def failed(method, url, **kwargs):
        if stage == "search" and url.endswith("Search") or stage == "ticket" and url.endswith("/1"):
            raise requests.Timeout("SECRET-PASSWORD")
        return original(method, url, **kwargs)

    transport.request = failed
    if stage == "disk":
        monkeypatch.setattr(Path, "replace", lambda *args: (_ for _ in ()).throw(OSError("disk failure")))
    if stage == "analytics":
        monkeypatch.setattr("parcom_analytics.live_cache.analyze_live", lambda *args: (_ for _ in ()).throw(ValueError("analytics failure")))
    errors, loaded = [], []
    worker.argument = period
    worker.failed.connect(errors.append)
    worker.succeeded.connect(loaded.append)
    worker.run()
    assert len(errors) == 1 and loaded == []
    assert "SECRET" not in errors[0]
    assert cache.path.read_bytes() == before
    assert client._live_state is state
    assert not cache.path.with_suffix(".json.tmp").exists()


def test_history_cache_invalidation_and_no_metadata_fallback(source):
    client, transport, _ = source
    assert client.get_history("1", changed="old") == []
    assert client.get_history("1", changed="old") == []
    assert counts(transport) == {"TicketHistory": 1}
    client.get_history("1", changed="new")
    client.invalidate_history(["1"])
    client.get_history("1", changed="new")
    client.get_history("1")
    client.get_history("1")
    assert counts(transport) == {"TicketHistory": 5}


def test_lazy_history_is_cached_across_unchanged_refresh(source):
    client, transport, period = source
    batch = fetch_live(client, period, Event())
    transport.reset()
    hydrated = load_history(client, batch, Event())
    assert hydrated.history_loaded and not batch.history_loaded
    assert counts(transport) == {"TicketSearch": 1, "TicketHistory": 8}
    commit_live(client, hydrated)
    refreshed = fetch_live(client, period, Event())
    transport.reset()
    load_history(client, refreshed, Event())
    assert counts(transport) == {"TicketSearch": 1}
    transport.changed = ["1"]
    changed = fetch_live(client, period, Event())
    transport.reset()
    load_history(client, changed, Event())
    assert counts(transport) == {"TicketSearch": 1, "TicketHistory": 1}


def test_failed_history_does_not_mutate_dashboard(source):
    client, transport, period = source
    batch = fetch_live(client, period, Event())
    before = deepcopy(batch.frames)
    original = transport.request

    def failed(method, url, **kwargs):
        if "/History/1" in url:
            raise requests.Timeout()
        return original(method, url, **kwargs)

    transport.request = failed
    with pytest.raises(ConnectionError):
        load_history(client, batch, Event())
    assert not batch.history_loaded and batch.agents == []
    for key, frame in before.items():
        pd.testing.assert_frame_equal(batch.frames[key], frame)


def test_cached_relative_values_advance_and_zero_timer_stays_zero():
    ticket = {"Age": 0, "UntilTime": 30, "_captured": datetime.now(ZURICH)-timedelta(seconds=60)}
    age_ticket(ticket)
    assert ticket["Age"] >= 60 and ticket["UntilTime"] <= -30
    ticket["UntilTime"] = 0
    age_ticket(ticket)
    assert ticket["UntilTime"] == 0


def test_session_expiry_preserves_disk_and_disallows_cached_data(jobs, tmp_path, source):
    client, transport, period = source
    cache = LiveCache(tmp_path)
    jobs(client, "refresh", period, cache=cache).run()
    before = cache.path.read_bytes()
    response = Response({})
    response.status_code = 401
    transport.request = lambda *args, **kwargs: response
    worker = jobs(client, "refresh", period, cache=cache)
    errors = []
    worker.failed.connect(errors.append)
    worker.run()
    assert errors and cache.path.read_bytes() == before
    assert client._live_state is None and client._session_id is None
    with pytest.raises(SessionExpired):
        client.get_history("1", changed="old")


def test_dashboard_history_loader_runs_off_gui_thread(qapp, tmp_path, source):
    from PySide6.QtCore import QTimer
    client, transport, period = source
    transport.latency = .015
    cache = LiveCache(tmp_path)
    controller = ConnectionController(client=client, cache=cache)
    controller.state = "online"
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(5)
    controller.refresh(period)
    finish(qapp, controller)
    assert len(ticks) > 3 and not cache.batch.history_loaded
    controller.load_history()
    finish(qapp, controller)
    timer.stop()
    assert cache.batch.history_loaded and transport.maximum <= 4
    restarted = LiveCache(tmp_path)
    assert restarted.batch.history_loaded and restarted.batch._state is None


def test_cache_and_logs_exclude_rest_secrets(jobs, tmp_path, caplog, source):
    client, transport, period = source
    original = transport.request

    def private(method, url, **kwargs):
        response = original(method, url, **kwargs)
        if "Ticket" in response.payload:
            response.payload["Ticket"][0].update(SessionID="SECRET-SESSION", Password="SECRET-PASSWORD", Article=[{"Body": "SECRET-ARTICLE"}])
        return response

    transport.request = private
    cache = LiveCache(tmp_path)
    jobs(client, "refresh", period, cache=cache).run()
    text = cache.path.read_text(encoding="utf-8") + caplog.text + repr(client._live_state.tickets)
    assert "SECRET" not in text and "synthetic-session" not in text
    assert "SessionID" not in text and "Password" not in text and "Article" not in text


def test_cancelled_refresh_never_commits(source):
    client, transport, period = source
    first = fetch_live(client, period, Event())
    state = client._live_state
    cancel = Event()
    cancel.set()
    with pytest.raises(ZnunyError, match="abgebrochen"):
        fetch_live(client, period, cancel)
    assert client._live_state is state and first._state is state


def test_unsafe_concurrency_is_rejected():
    for limit in (0, 6, 20, True):
        with pytest.raises(ValueError):
            ZnunyClient(concurrency=limit)


def test_invalidation_during_history_request_cannot_repopulate_stale_cache(source):
    client, transport, _ = source
    entered, release = Event(), Event()
    original = transport.request

    def blocked(method, url, **kwargs):
        entered.set()
        assert release.wait(2)
        return original(method, url, **kwargs)

    transport.request = blocked
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.get_history, "1", changed="old")
        assert entered.wait(2)
        client.invalidate_history(["1"])
        release.set()
        assert pending.result() == []
    assert "1" not in client._history_cache
    client.get_history("1", changed="old")
    assert counts(transport) == {"TicketHistory": 2}


def test_late_response_cannot_damage_a_replacement_session(source):
    client, transport, _ = source
    entered, release = Event(), Event()
    original = transport.request

    def blocked(method, url, **kwargs):
        entered.set()
        assert release.wait(2)
        return original(method, url, **kwargs)

    transport.request = blocked
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.get_history, "1", changed="old")
        assert entered.wait(2)
        with client._lock:
            client._generation += 1
            client._session_id = "replacement-session"
            client.connected = True
        release.set()
        with pytest.raises(SessionExpired):
            pending.result()
    assert client._session_id == "replacement-session" and client.connected
    assert not client._history_cache


def test_obsolete_session_cannot_replace_disk_cache(jobs, tmp_path, source):
    client, _, period = source
    cache = LiveCache(tmp_path)
    worker = jobs(client, "refresh", period, cache=cache)
    worker.run()
    before = cache.path.read_bytes()
    staged = fetch_live(client, period, Event(), commit=False)
    client.clear_cache()
    with pytest.raises(ZnunyError, match="Sitzung"):
        worker._publish(staged)
    assert cache.path.read_bytes() == before and client._live_state is None


def test_cancel_before_disk_replace_preserves_last_snapshot(jobs, tmp_path, monkeypatch, source):
    client, _, period = source
    cache = LiveCache(tmp_path)
    worker = jobs(client, "refresh", period, cache=cache)
    worker.run()
    before, state = cache.path.read_bytes(), client._live_state
    original = Path.open

    def cancelling(path, *args, **kwargs):
        if path.name.endswith(".json.tmp"):
            worker.cancel.set()
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", cancelling)
    worker.argument = period
    worker.run()
    assert cache.path.read_bytes() == before and client._live_state is state


def test_history_attribution_pending_timer_and_zero_metrics_preserved(source):
    from parcom_analytics.agents import metrics
    client, transport, period = source
    original = transport.request
    histories = {
        "1": [{"HistoryType": "StateUpdate", "CreateTime": "2026-10-02 08:00:00", "CreateBy": 69, "StateID": 13}],
        "2": [{"HistoryType": "StateUpdate", "CreateTime": "2026-10-02 08:00:00", "CreateBy": 1, "StateID": 13}],
        "4": [{"HistoryType": "SetPendingTime", "CreateTime": "2026-10-02 08:00:00", "CreateBy": 61, "Name": "%%2026-10-02 10:00:00%%"}],
        "9": [{"HistoryType": "SendAnswer", "CreateTime": "2026-10-02 08:00:00", "CreateBy": 69}],
    }

    def semantic(method, url, **kwargs):
        response = original(method, url, **kwargs)
        if url.endswith("Search"):
            filters = kwargs["json"]
            if "TicketCloseTimeNewerDate" in filters:
                response.payload["TicketIDs"] = ["1", "2"] if filters["TicketCloseTimeNewerDate"] >= "2026-09-29" else []
            elif filters.get("StateType") == "pending reminder":
                response.payload["TicketIDs"] = ["3", "4"]
            elif "TicketLastChangeTimeNewerDate" in filters:
                response.payload["TicketIDs"] = ["9"]
            elif isinstance(filters.get("StateType"), list):
                response.payload["TicketIDs"] = ["3", "4"]
        elif "/History/" in url:
            ticket_id = url.rsplit("/", 1)[-1]
            response.payload["TicketHistory"][0]["History"] = histories.get(ticket_id, [])
        elif "Ticket" in response.payload:
            ticket = response.payload["Ticket"][0]
            ticket.update(CustomerID="00325", OwnerID=61, Owner="owner", Type="Actual server type", TypeID=7)
            if ticket["TicketID"] in ("1", "2"):
                ticket.update(StateType="closed", State="ohne Rückmeldung geschlossen", StateID=13, Closed="2026-10-02 08:00:00")
            elif ticket["TicketID"] == "3":
                ticket.update(StateType="pending auto")
            elif ticket["TicketID"] == "4":
                ticket.update(StateType="pending reminder", UntilTime=None)
            elif ticket["TicketID"] == "9":
                ticket.update(Created="2026-09-01 08:00:00", FirstResponse="2026-10-02 08:00:00")
        return response

    transport.request = semantic
    batch = fetch_live(client, period, Event())
    assert counts(transport)["TicketHistory"] == 1  # Only the absent pending timer.
    assert batch.frames[7]["TicketID"].tolist() == ["4"]
    assert batch.frames[7].iloc[0]["Timer"] == "Überfällig"
    assert batch.frames[2]["StateType"].tolist() == ["closed", "closed"]
    assert batch.frames[3]["Kundennummer"].tolist() == ["Kein Kunde zugewiesen"]*2
    hydrated = load_history(client, batch, Event())
    assert hydrated.frames[2]["ClosedByID"].tolist() == ["69", "1"]
    result = {item["id"]: item for item in metrics(hydrated, {"61", "69"})}
    assert result["61"]["Geschlossen"] == 0
    assert result["69"]["Geschlossen"] == 1 and result["69"]["Erstantworten"] == 1
    assert result["69"]["Reaktionszeit (Min.)"] == 0
    assert "9" in hydrated._state.tickets  # Activity outside dashboard memberships.


def test_restored_lazy_snapshot_refreshes_before_history(qapp, jobs, tmp_path, source):
    client, transport, period = source
    cache = LiveCache(tmp_path)
    jobs(client, "refresh", period, cache=cache).run()
    restored = LiveCache(tmp_path)
    assert not restored.batch.history_loaded and restored.batch._state is None
    client.clear_cache()
    transport.reset()
    controller = ConnectionController(client=client, cache=restored)
    controller.state = "online"
    controller.load_history()
    finish(qapp, controller)
    assert restored.batch.history_loaded and counts(transport)["TicketGet"] == 8
