from datetime import datetime, timedelta

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from parcom_analytics.analytics import DataError
from parcom_analytics.periods import PRESETS, TimeRange, ZURICH
from parcom_analytics.timeline import Timeline


def test_exact_periods_buckets_and_previous_at_month_end():
    end = datetime(2026, 10, 6, 14, 10, tzinfo=ZURICH)
    for key in PRESETS:
        period = TimeRange.preset(key, end)
        assert period.end == end
        assert period.buckets()[0] == period.start
        assert period.buckets()[-1] == end
    period = TimeRange.preset("3M", end)
    assert [p.month for p in period.buckets()] == [7, 8, 9, 10]
    assert all(p.day == 6 and p.hour == 14 for p in period.buckets())
    assert TimeRange.preset("1M", datetime(2026, 3, 31, tzinfo=ZURICH)).start.day == 28
    with pytest.raises(DataError):
        TimeRange(end - timedelta(hours=23), end)
    with pytest.raises(DataError):
        TimeRange(end - timedelta(days=367), end)


def test_timeline_snap_custom_zoom_both_handles_and_resize(qapp):
    widget = Timeline()
    widget.resize(620, 120)
    widget.show()
    qapp.processEvents()
    track = widget.track
    assert track.key == "1W"
    for key in PRESETS:
        QTest.mouseClick(track, Qt.MouseButton.LeftButton, pos=QPoint(round(track.x(PRESETS.index(key))), 22))
        assert track.key == key and track.mode == "normal"
    custom = TimeRange(datetime(2026, 8, 15, 9, tzinfo=ZURICH), datetime(2026, 10, 3, 14, tzinfo=ZURICH))
    for handle in (0, 1):
        track.apply_custom(custom)
        assert track.period() == custom and track.handles() == (track.x(0), track.x(6))
        widget.resize(700 if handle == 0 else 520, 120)
        qapp.processEvents()
        origin = QPoint(round(track.handles()[handle]), 22)
        target = QPoint(round(track.x(3)), 22)
        QTest.mousePress(track, Qt.MouseButton.LeftButton, pos=origin)
        QTest.mouseMove(track, target)
        QTest.mouseRelease(track, Qt.MouseButton.LeftButton, pos=target)
        assert track.mode == "normal" and track.key == "1M"
    track.apply_custom(custom)
    assert widget.period() == custom
    widget.sync_controls()
    assert widget.period() == custom
    widget.close()
