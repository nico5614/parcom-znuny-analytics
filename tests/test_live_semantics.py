from datetime import datetime, timedelta
from threading import Event
from unittest.mock import Mock

import pytest

from parcom_analytics.live_data import fetch_live, normalize_tickets, timer
from parcom_analytics.live_metrics import analyze_live, period_series
from parcom_analytics.live_cache import LiveCache
from parcom_analytics.periods import TimeRange, ZURICH


def test_live_scope_custom_closed_states_waiting_escalation_and_comparison(tmp_path):
    client = Mock()
    client.search_tickets.side_effect = [["1"],["2"],["3","4"],["3","4"],["3"],["5"],["6"]]
    raw = [dict(TicketID=str(i), TicketNumber=str(i), Title="Synthetisch", Age=0, Queue="PBX", Type="Unclassified",
                Created="2026-09-30 10:00:00", Closed="2026-10-01 10:00:00", FirstResponseInMin=0, SolutionInMin=10,
                FirstResponseTimeEscalation=0, StateType="closed" if i in (2,6) else "pending auto" if i==4 else "pending reminder",
                State="ohne Rückmeldung geschlossen" if i==2 else "pending reminder", UntilTime=-60, Lock="lock") for i in range(1,7)]
    raw[2]["EscalationTime"] = -600
    for item in raw[4:]:
        item["Created"],item["Closed"] = "2026-09-24 10:00:00","2026-09-25 10:00:00"
    client.get_tickets.return_value = raw
    period=TimeRange.preset("1W",datetime(2026,10,6,14,tzinfo=ZURICH))
    batch=fetch_live(client,period,Event())
    assert len(batch.frames[2])==1 and batch.frames[2].iloc[0]["Status"]=="ohne Rückmeldung geschlossen"
    assert batch.frames[7]["TicketID"].tolist()==["3"]
    assert len(batch.frames[3])==2
    assert len(batch.previous[1])==1
    assert client.search_tickets.call_args_list[4].args[0]["TicketEscalationTimeOlderMinutes"]==1
    assert client.search_tickets.call_args_list[0].args[0]["TicketCreateTimeNewerDate"]=="2026-09-29 12:00:00"
    result=analyze_live(4,batch.frames[4],period)
    assert result.chart.to_dict()=={"Eskaliert":1,"Nicht eskaliert":1}
    assert result.details.iloc[0]["Typ"]=="Unclassified"
    cache=LiveCache(tmp_path); cache.update(batch)
    restarted=LiveCache(tmp_path)
    assert restarted.batch.period==period and restarted.reports()[1].comparable
    assert restarted.management().metrics["Überfällig + gesperrt"]=="1"


def test_timer_dst_zero_missing_and_customer_mapping():
    captured=datetime(2026,10,25,2,30,tzinfo=ZURICH,fold=0)
    status,due=timer(3600,captured)
    assert status=="Aktiv" and due.endswith("+01:00") and "02:30" in due
    assert timer(-60,captured)[0]=="Überfällig"
    assert timer(0,captured)==("Kein Timer",None)
    assert timer(None,captured)==("Unbekannt",None)
    frame=normalize_tickets([{"CustomerID":"00325","FirstResponseInMin":0}, {"CustomerID":"00421"}])
    assert frame["Kundennummer"].tolist()==["Kein Kunde zugewiesen","00421"]
    assert frame.iloc[0]["Erstantwortzeit in Minuten"]==0


def test_rolling_buckets_are_distinct_and_preserve_zero_days():
    end=datetime(2026,10,6,14,tzinfo=ZURICH)
    period=TimeRange.preset("3M",end)
    frame=normalize_tickets([{"Created":"2026-07-07 10:00:00"}, {"Created":"2026-09-07 10:00:00"}])
    series=period_series(frame,1,period)
    assert series.tolist()==[1,0,1] and len(set(series.index))==3
    assert series.index.tolist()==["06.07.–06.08.","06.08.–06.09.","06.09.–06.10."]
