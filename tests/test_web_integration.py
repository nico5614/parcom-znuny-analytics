"""Exercise the real optimized loader through the Qt-free desktop bridge."""

from datetime import datetime

import pytest

from parcom_analytics.live_cache import LiveCache
from parcom_analytics.periods import TimeRange, ZURICH
from parcom_analytics.web.bridge import DesktopBridge
from parcom_analytics.web.settings import Settings
from parcom_analytics.znuny import ZnunyClient
from performance_benchmark import BenchmarkTransport


@pytest.fixture
def integrated(tmp_path):
    transport = BenchmarkTransport(count=8, latency=0)
    client = ZnunyClient(transport)
    client._session_id = "synthetic-session"
    client.connected = True
    bridge = DesktopBridge(client=client, root=tmp_path, cache=LiveCache(tmp_path), settings=Settings(tmp_path))
    bridge._username = "synthetic"
    period = TimeRange.preset("1W", datetime(2026, 10, 6, 14, tzinfo=ZURICH))
    selection = {"preset": None, "start": period.start.isoformat(), "end": period.end.isoformat()}
    return bridge, transport, selection


def counts(transport):
    return {key: value["count"] for key, value in transport.calls.items()}


def test_web_refresh_uses_delta_and_navigation_does_not_fetch(integrated):
    bridge, transport, selection = integrated
    assert bridge.refresh(selection)["ok"]
    assert counts(transport) == {"TicketSearch": 7, "TicketGet": 8}
    assert not bridge._cache.batch.history_loaded
    transport.reset()
    for _ in range(2):
        assert bridge.getOverview()["ok"]
        for kpi in range(1, 8):
            assert bridge.getAnalysis(kpi)["ok"]
    assert counts(transport) == {}
    assert bridge.refresh(selection)["ok"]
    assert counts(transport) == {"TicketSearch": 8}
    transport.reset()
    transport.changed = ["1", "2"]
    assert bridge.refresh(selection)["ok"]
    assert counts(transport) == {"TicketSearch": 8, "TicketGet": 2}


def test_web_disk_failure_preserves_sync_watermark(integrated, monkeypatch):
    bridge, transport, selection = integrated
    assert bridge.refresh(selection)["ok"]
    before = bridge._cache.path.read_bytes()
    state = bridge._client._live_state
    revision = bridge._revision
    transport.changed = ["1"]
    def fail(*args, **kwargs):
        raise OSError("synthetic disk failure")
    monkeypatch.setattr(bridge._cache, "update", fail)
    assert not bridge.refresh(selection)["ok"]
    assert bridge._cache.path.read_bytes() == before
    assert bridge._client._live_state is state
    assert bridge._revision == revision


def test_web_agents_load_history_once_and_reuse_it(integrated):
    bridge, transport, selection = integrated
    assert bridge.refresh(selection)["ok"]
    transport.reset()
    result = bridge.getAgents()
    assert result["ok"] and result["data"]["historyLoaded"]
    assert counts(transport)["TicketHistory"] == 8
    transport.reset()
    assert bridge.getAgents()["ok"]
    assert bridge.getAgents("61")["ok"]
    assert counts(transport) == {}
    assert bridge.refresh(selection)["ok"]
    transport.reset()
    assert bridge.getAgents()["ok"]
    assert counts(transport) == {"TicketSearch": 1}


def test_web_offline_without_history_never_claims_zero_activity(integrated):
    bridge, _, selection = integrated
    assert bridge.refresh(selection)["ok"]
    assert bridge.continueOffline()["ok"]
    result = bridge.getAgents()["data"]
    assert not result["historyLoaded"]
    assert result["metrics"][2]["value"] == "–"
    assert all(row["Geschlossen"] is None for row in result["rows"])
    assert "nicht verfügbar" in result["rankingNote"]
