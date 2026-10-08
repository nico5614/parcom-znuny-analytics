from datetime import datetime, timezone
import json

import pytest
from unittest.mock import Mock

from parcom_analytics.web.bridge import DesktopBridge
from parcom_analytics.web.serialization import json_value
from parcom_analytics.znuny import LoginError, ConnectionError


def test_serialization_preserves_zero_and_normalizes_nonfinite():
    value = json_value({"zero": 0, "missing": None, "values": [float("nan"), float("inf")],
                        "at": datetime(2026, 10, 7, tzinfo=timezone.utc)})
    assert json.loads(json.dumps(value, allow_nan=False)) == {
        "zero": 0, "missing": None, "values": [None, None], "at": "2026-10-07T00:00:00+00:00"}


@pytest.mark.parametrize("value", [object(), {1: "invalid key"}, datetime(2026, 1, 1)])
def test_serialization_rejects_implicit_backend_objects_and_naive_dates(value):
    with pytest.raises((TypeError, ValueError)):
        json_value(value)


def test_bridge_round_trip_requires_renderer_acknowledgement():
    events = []
    bridge = DesktopBridge(events.append)
    assert not bridge.confirmProbe(0)
    reply = bridge.probe()
    assert reply["sequence"] == events[0]["sequence"] == 1
    assert not bridge._probe_confirmed.is_set()
    assert not bridge.confirmProbe(True)
    assert not bridge.confirmProbe(99)
    assert bridge.confirmProbe(1)
    assert bridge._probe_confirmed.is_set()
    assert set(bridge.getAppInfo()) == {"name", "version", "python", "renderer", "packaged"}


def test_login_dto_never_returns_credentials_and_logout_cleans_session():
    client = Mock()
    client.login.return_value = {"SessionID": "synthetic-session-must-not-leak"}
    bridge = DesktopBridge(client=client)
    reply = bridge.login(" test-agent ", "synthetic-password")
    assert reply == {"ok": True, "data": {"username": "test-agent"}}
    client.login.assert_called_once_with("test-agent", "synthetic-password")
    assert "synthetic-password" not in repr(vars(bridge))
    bridge.logout()
    client.logout.assert_called_once()
    assert bridge._username is None


@pytest.mark.parametrize("error, kind", [(LoginError("secret"), "authentication"), (ConnectionError("secret"), "network"), (RuntimeError("secret"), "server")])
def test_login_error_types_are_distinct_and_sanitized(error, kind):
    client = Mock()
    client.login.side_effect = error
    reply = DesktopBridge(client=client).login("test-agent", "synthetic-password")
    assert not reply["ok"]
    assert reply["error"]["kind"] == kind
    assert "secret" not in json.dumps(reply)
