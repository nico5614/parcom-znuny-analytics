from pathlib import Path
from threading import Event, Thread
import json

import pytest

from parcom_analytics.agents import metrics
from parcom_analytics.live_cache import LiveCache
from parcom_analytics.web.bridge import DesktopBridge
from parcom_analytics.web.dto import agents_dto
from parcom_analytics.web.settings import Settings
from parcom_analytics.web.validation import ValidationClient, validation_batch


@pytest.fixture
def bridge(tmp_path):
    cache = LiveCache(tmp_path)
    cache.update(validation_batch())
    client = ValidationClient()
    bridge = DesktopBridge(root=tmp_path, cache=cache, settings=Settings(tmp_path), client=client, fetch=validation_batch)
    assert bridge.login("validation", "validation")["ok"]
    return bridge


def test_agents_match_backend_and_team_persists_without_system(bridge):
    result = bridge.getAgents()["data"]
    expected = metrics(bridge._cache.batch, result["selected"])
    assert sum(row["Geschlossen"] for row in result["rows"]) == sum(row["Geschlossen"] for row in expected)
    assert "1" not in result["selected"]
    assert "99" not in result["selected"]
    assert bridge.setTeam(["61", "99"])["ok"]
    after = bridge.getAgents()["data"]
    assert after["selected"] == ["61", "99"]
    assert next(row["label"] for row in after["rows"] if row["id"] == "99") == "test.missing · Kürzel nicht zugeordnet"
    assert bridge._settings.get("team_selection") == ["61", "99"]
    assert not bridge.setTeam(["1"])["ok"]
    assert not bridge.getAgents("not-an-id")["ok"]
    assert not bridge.getAgents("__dict__")["ok"]
    assert bridge.setTeam([])["ok"]
    assert bridge.getAgents()["data"]["table"]["rows"] == []


def test_refresh_replaces_complete_cache_only_and_returns_idle_state(bridge):
    reply = bridge.refresh({"preset": "1M"})
    assert reply["ok"] and not reply["data"]["busy"]
    assert reply["data"]["revision"] == 1
    assert bridge._cache.batch.period.label == bridge.getPeriod()["label"]
    assert bridge.getPeriod()["preset"] == "1M"
    previous = bridge._cache.path.read_bytes()
    bridge._fetch = lambda period: (_ for _ in ()).throw(RuntimeError("synthetic secret"))
    failed = bridge.refresh({"preset": "1W"})
    assert not failed["ok"] and "secret" not in str(failed)
    assert bridge._cache.path.read_bytes() == previous
    assert not bridge.getState()["busy"]


def test_custom_period_stays_exact_after_a_cached_restart(bridge):
    from datetime import timedelta
    from parcom_analytics.periods import now
    end = now()
    selection = {"preset": None, "start": (end-timedelta(days=2, hours=3)).isoformat(), "end": end.isoformat()}
    assert bridge.refresh(selection)["ok"]
    restored = DesktopBridge(root=bridge._root)
    assert restored.getPeriod()["preset"] is None
    assert restored.getPeriod()["start"] == selection["start"]
    assert restored.getPeriod()["end"] == selection["end"]


def test_logout_cancels_refresh_before_commit_and_clears_private_session(bridge):
    entered, release = Event(), Event()
    def fetch(period):
        entered.set()
        assert release.wait(5)
        return validation_batch(period)
    bridge._fetch = fetch
    results = []
    worker = Thread(target=lambda: results.append(bridge.refresh({"preset": "1T"})))
    worker.start()
    assert entered.wait(5)
    cleanup = Thread(target=bridge.logout)
    cleanup.start()
    assert bridge._cancel.wait(5)
    release.set()
    worker.join(5); cleanup.join(5)
    assert results[0]["error"]["kind"] == "cancelled"
    assert bridge._revision == 0
    assert bridge._client._session_id is None
    assert not bridge.getOverview()["ok"]
    assert bridge.continueOffline()["ok"]
    assert bridge.getOverview()["ok"]


@pytest.mark.parametrize("target", ["overview", "5"])
def test_pdf_uses_existing_renderer_in_offscreen_worker(bridge, tmp_path, target, monkeypatch):
    import builtins
    original = builtins.__import__
    def no_qt(name, *args, **kwargs):
        if name.startswith(("PySide6", "shiboken6")):
            raise AssertionError("PDF export loaded Qt in the host")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", no_qt)
    path = tmp_path / f"report-{target}.pdf"
    bridge._choose_save = lambda filename: str(path)
    reply = bridge.exportPdf(target)
    assert reply == {"ok": True, "data": {"cancelled": False, "filename": path.name}}
    assert path.read_bytes().startswith(b"%PDF-")
    assert path.stat().st_size > 10000


def test_export_cancel_validation_and_no_credentials_in_dtos(bridge):
    bridge._choose_save = lambda filename: None
    assert bridge.exportPdf("overview")["data"]["cancelled"]
    assert not bridge.exportPdf("../../secret")["ok"]
    assert not bridge.exportPdf("5", "invented")["ok"]
    result = json.dumps([bridge.getOverview(), bridge.getAnalysis(5), bridge.getAgents(), bridge.getExportOptions()], allow_nan=False)
    assert "synthetic-validation-session" not in result
    assert "SessionID" not in result
    assert "Password" not in result


def test_pdf_worker_failure_does_not_break_dashboard(bridge, tmp_path, monkeypatch):
    from parcom_analytics.web import pdf_export
    def fail(*args):
        raise RuntimeError("worker unavailable")
    monkeypatch.setattr(pdf_export, "run_export", fail)
    bridge._choose_save = lambda filename: str(tmp_path / filename)
    assert bridge.exportPdf("overview")["error"]["kind"] == "export"
    assert bridge.getOverview()["ok"]
    assert not bridge.getState()["busy"]


def test_failed_reauthentication_does_not_leave_authorized_username(bridge):
    assert not bridge.login("wrong", "wrong")["ok"]
    assert bridge._username is None
    assert not bridge.getOverview()["ok"]
