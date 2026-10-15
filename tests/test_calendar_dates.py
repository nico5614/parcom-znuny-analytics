from datetime import date, datetime, timedelta, timezone
import pandas as pd
from parcom_analytics.periods import TimeRange, ZURICH
from parcom_analytics.live_metrics import period_series

def test_week_has_today_and_midnight_buckets():
    period = TimeRange.preset('1W', datetime(2026, 10, 14, 13, 41, tzinfo=ZURICH))
    frame = pd.DataFrame({'Erstellt': ['2026-10-08T00:00:00+02:00', '2026-10-13T23:59:59+02:00', '2026-10-14T00:00:00+02:00', '2026-10-14T13:41:00+02:00']})
    series = period_series(frame, 1, period)
    assert series.index.tolist() == ['08.10.', '09.10.', '10.10.', '11.10.', '12.10.', '13.10.', '14.10.']
    assert series.tolist() == [1, 0, 0, 0, 0, 1, 2]
    assert series.sum() == len(frame)

def test_custom_includes_whole_end_date_and_single_day():
    period = TimeRange.dates(date(2026, 9, 1), date(2026, 9, 12))
    assert period.start.hour == 0 and period.end.hour == 23
    assert len(period.buckets()) == 13
    one = TimeRange.dates(date(2026, 9, 12), date(2026, 9, 12))
    assert one.label == '12.09.2026 – 12.09.2026'
    assert len(one.buckets()) == 2

def test_calendar_buckets_follow_dst_without_missing_or_double_tickets():
    period = TimeRange.dates(date(2026, 3, 28), date(2026, 3, 30))
    edges = period.buckets()
    assert (edges[2].astimezone(timezone.utc)-edges[1].astimezone(timezone.utc)) == timedelta(hours=23)
    frame = pd.DataFrame({'Erstellt': ['2026-03-28T23:59:59+01:00', '2026-03-29T00:00:00+01:00', '2026-03-30T00:00:00+02:00']})
    assert period_series(frame, 1, period).tolist() == [1, 1, 1]
