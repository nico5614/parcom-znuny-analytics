from datetime import timedelta
from unittest.mock import Mock
import json

import pytest

from parcom_analytics.live_cache import LiveCache
from parcom_analytics.periods import TimeRange, now
from parcom_analytics.web.bridge import DesktopBridge
from parcom_analytics.web.dto import analysis_dto, overview, period_dto, resolve_period, ticket_details
from parcom_analytics.web.settings import Settings
from parcom_analytics.web.validation import validation_batch


@pytest.fixture
def web_data(tmp_path):
    cache = LiveCache(tmp_path)
    cache.update(validation_batch())
    settings = Settings(tmp_path)
    return cache, settings


def test_overview_uses_existing_management_values_and_keeps_score_unavailable(web_data):
    cache, settings = web_data
    dto = overview(cache, settings)
    assert dto["metrics"][1]["value"] == cache.management().metrics["Neue Tickets"]
    assert dto["metrics"][3]["value"] == cache.management().metrics["Abschlussverhältnis (geschlossen / neu)"]
    assert dto["metrics"][0]["value"] == "–"
    assert dto["score"]["issue"]
    assert "SessionID" not in json.dumps(dto, allow_nan=False)
    assert dto["action"]["total"] == 6


def test_analysis_filter_comparison_pagination_and_zero_minutes(web_data):
    cache, _ = web_data
    response = analysis_dto(cache, 5)
    assert response["table"]["total"] == 24
    assert any("0 min" in row["cells"] for row in response["table"]["rows"])
    filtered = analysis_dto(cache, 5, "Auftrag")
    assert filtered["table"]["total"] == int(cache.batch.frames[5]["Typ"].eq("Auftrag").sum())
    assert all(row["cells"][3] == "Auftrag" for row in filtered["table"]["rows"])
    assert analysis_dto(cache, 5, page=1)["table"]["rows"] == []
    assert analysis_dto(cache, 5)["history"]["labels"][0] != analysis_dto(cache, 5)["history"]["labels"][1]
    assert analysis_dto(cache, 5)["history"]["unitLabel"] == "Minuten"
    assert any(row["maximum"] for row in response["table"]["rows"])
    for kpi in range(1, 8):
        json.dumps(analysis_dto(cache, kpi), allow_nan=False)


def test_ticket_details_customer_convention_and_safe_deep_link(web_data, monkeypatch):
    cache, settings = web_data
    ticket = ticket_details(cache, "51")
    assert next(field["value"] for field in ticket["fields"] if field["label"] == "Kundennummer") == "Kein Kunde zugewiesen"
    bridge = DesktopBridge(cache=cache, settings=settings, client=Mock())
    bridge._username = "validation"
    opened = Mock()
    monkeypatch.setattr("parcom_analytics.web.bridge.webbrowser.open", opened)
    assert bridge.openTicket("51")["ok"]
    opened.assert_called_once_with("https://znuny.parcom.ch/otrs/index.pl?Action=AgentTicketZoom;TicketID=51")
    assert not bridge.openTicket("1;SessionID=secret")["ok"]
    assert not bridge.openTicket("999999")["ok"]
    assert bridge.getTicketDetails("200")["ok"]


def test_change_check_does_not_replace_cache(web_data):
    cache, settings = web_data
    client = Mock(connected=True)
    client.search_tickets.return_value = ["1"]
    bridge = DesktopBridge(cache=cache, settings=settings, client=client)
    bridge._username = "validation"
    previous = cache.path.read_bytes()
    assert bridge.checkChanges()["newData"]
    assert cache.path.read_bytes() == previous
    assert bridge.getState()["revision"] == 0
    assert "TicketLastChangeTimeNewerDate" in client.search_tickets.call_args.args[0]


def test_periods_are_resolved_in_python_and_reject_invalid_intervals():
    period = resolve_period({"preset": "1W"})
    assert period.end - period.start == timedelta(days=7)
    custom = resolve_period({"preset": None, "start": (now() - timedelta(days=2)).isoformat(), "end": now().isoformat()})
    assert period_dto(custom)["preset"] is None
    with pytest.raises(ValueError):
        resolve_period({"preset": "999J"})
    with pytest.raises(ValueError):
        resolve_period({"preset": None, "start": now().isoformat(), "end": now().isoformat()})


def test_settings_round_trip_and_existing_qt_settings(tmp_path, qapp):
    from PySide6.QtCore import QSettings
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("team_selection", json.dumps(["3", "61"]))
    settings.setValue("reduce_motion", True)
    settings.sync()
    adapter = Settings(tmp_path)
    assert adapter.get("team_selection") == ["3", "61"]
    adapter.set({"team_selection": ["69"], "agent_registry": {"69": {"id": "69", "code": "DRE"}}})
    settings.sync()
    assert json.loads(settings.value("team_selection")) == ["69"]
