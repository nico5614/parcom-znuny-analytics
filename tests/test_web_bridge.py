from datetime import datetime, timezone
import json

import pytest

from parcom_analytics.web.bridge import DesktopBridge
from parcom_analytics.web.serialization import json_value


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
