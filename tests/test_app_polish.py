from dataclasses import replace
from datetime import datetime, timedelta
from unittest.mock import Mock

from PySide6.QtGui import QDesktopServices
from matplotlib.figure import Figure

from parcom_analytics.connection import ConnectionController
from parcom_analytics.live_cache import LiveCache
from parcom_analytics.periods import TimeRange, ZURICH
from parcom_analytics.storage import LocalStore, period_label
from parcom_analytics.ui import MainWindow, FrameModel, open_ticket
from parcom_analytics.charts import draw_chart
from parcom_analytics.pdf_export import export_pdf
from test_connection import finish
from test_live_cache import batch
from test_reports import pdf_text


def test_lightweight_change_check_never_replaces_cache(qapp,tmp_path,batch):
    cache=LiveCache(tmp_path);cache.update(batch)
    before=cache.path.read_bytes()
    client=Mock(connected=True)
    client.search_tickets.return_value=[]
    controller=ConnectionController(client=client,cache=cache)
    controller.state="online"
    detected,busy,loaded=[],[],[]
    controller.changesDetected.connect(detected.append)
    controller.busyChanged.connect(busy.append)
    controller.loaded.connect(loaded.append)
    controller.check_changes();finish(qapp,controller)
    assert detected==[False] and busy==[] and loaded==[]
    client.search_tickets.return_value=["1"]
    controller.check_changes();finish(qapp,controller)
    assert detected==[False,True] and cache.path.read_bytes()==before
    assert client.search_tickets.call_args.kwargs["limit"]==1
    assert "TicketLastChangeTimeNewerDate" in client.search_tickets.call_args.args[0]
    client.get_tickets.assert_not_called()


def test_refresh_rolling_now_and_fixed_custom_and_change_banner(qapp,tmp_path,monkeypatch):
    import parcom_analytics.periods as periods
    clock=datetime(2026,10,6,14,tzinfo=ZURICH)
    monkeypatch.setattr(periods,"now",lambda:clock)
    window=MainWindow(LocalStore(tmp_path),require_login=True)
    window.connection.state="online"
    window.connection.refresh=Mock()
    window.refresh_live()
    first=window.connection.refresh.call_args.args[0]
    clock+=timedelta(minutes=10)
    window.refresh_live()
    assert window.connection.refresh.call_args.args[0].end-first.end==timedelta(minutes=10)
    custom=TimeRange(clock-timedelta(days=3),clock-timedelta(days=1))
    window.timeline.track.apply_custom(custom)
    clock+=timedelta(minutes=10)
    window.refresh_live()
    assert window.connection.refresh.call_args.args[0]==custom
    window._changes_detected(True)
    assert not window.change_banner.isHidden() and window.change_timer.interval()==120000
    window.close()


def test_live_details_safe_deep_link_and_paginated_export(qapp,tmp_path,batch,monkeypatch):
    period=TimeRange.preset("1M")
    batch=replace(batch,period=period,captured_at=period.end.isoformat(),snapshot_is_now=True)
    for frame in batch.frames.values():
        frame["TicketID"]=[str(i) for i in range(len(frame))]
        frame["Aktuell eskaliert"]=[1,0,0,0,0,0]
        frame["OwnerID"]="61"
    cache=LiveCache(tmp_path);cache.update(batch)
    report=cache.reports()[4]
    model=FrameModel(report.analysis.details)
    opened=[]
    monkeypatch.setattr(QDesktopServices,"openUrl",lambda url:opened.append(url.toString()) or True)
    assert open_ticket(model,model.index(0,0))
    assert opened==["https://znuny.parcom.ch/otrs/index.pl?Action=AgentTicketZoom;TicketID=0"]
    assert "NKO" in report.analysis.details["Besitzer"].tolist()
    figure=Figure();draw_chart(figure,report.analysis)
    target=tmp_path/"details.pdf"
    export_pdf(target,report.analysis,period_label(report.record),figure,report)
    text=pdf_text(target)
    for expected in ("NKO","Eskalation","ZnunyLive","Datenstand:"):
        assert expected in text
    assert "SessionID" not in text and "SECRET" not in text
