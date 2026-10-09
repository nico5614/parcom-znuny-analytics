from datetime import datetime
from unittest.mock import Mock

from PySide6.QtCore import QSettings, Qt

from parcom_analytics.agents import closed_event, response_actor, state_types, code, identity, metrics
from parcom_analytics.periods import ZURICH
from parcom_analytics.znuny import ZnunyClient, BASE_URL
from test_live_cache import batch


def event(kind, stamp, actor, **values):
    return {"HistoryType":kind,"CreateTime":stamp,"CreateBy":actor,**values}


def test_final_close_reopen_system_and_localized_state():
    start,end=datetime(2026,10,1,tzinfo=ZURICH),datetime(2026,10,7,tzinfo=ZURICH)
    mapping=state_types([{"State":"ohne Rückmeldung geschlossen","StateID":13,"StateType":"closed"}])
    history=[event("StateUpdate","2026-10-02 08:00:00",61,StateID=13),
             event("StateUpdate","2026-10-03 08:00:00",69,Name="%%open%%closed successful%%")]
    assert closed_event(history,start,end,mapping)[0]=="69"
    history.append(event("StateUpdate","2026-10-04 08:00:00",1,Name="%%pending auto close+%%closed successful%%"))
    assert closed_event(history,start,end,mapping)[0]=="1"
    assert code(75)=="LRO" and code(81)=="ID 81" and identity(61)["name"]=="Nico Köchli"


def test_response_actor_window_ambiguity_and_owner_never_used():
    ticket={"FirstResponse":"2026-10-02 08:00:00","OwnerID":61}
    history=[event("SendAnswer","2026-10-02 08:00:05",69),event("OwnerUpdate","2026-10-02 08:00:00",61)]
    assert response_actor(ticket,history)[0]=="69"
    history.append(event("EmailAgent","2026-10-02 07:59:55",70))
    assert response_actor(ticket,history)[0] is None
    assert response_actor(ticket,[event("SendAnswer","2026-10-02 08:00:06",69)])[0] is None
    assert response_actor(ticket,[event("SendAnswer","2026-10-02 08:00:00",1)])[0] is None


def test_history_and_session_routes_preserve_tls():
    transport=Mock()
    transport.request.return_value=Mock(status_code=200,json=Mock(return_value={"TicketHistory":[{"TicketID":42,"History":[]}]}))
    client=ZnunyClient(transport);client._session_id="synthetic"
    assert client.get_history(42)==[]
    assert transport.request.call_args.args==("GET",BASE_URL+"/Ticket/History/42")
    assert transport.request.call_args.kwargs["verify"] is True
    client.session_valid()
    assert transport.request.call_args.args==("GET",BASE_URL+"/Session/synthetic")


def test_team_selection_persists_unknown_discovery_and_codes(qapp,tmp_path,batch):
    from parcom_analytics.agents_ui import AgentsPage
    from parcom_analytics.live_cache import LiveCache
    cache=LiveCache(tmp_path)
    batch.identities=[identity(61),identity(81)]
    batch.agents=[{"TicketID":"5","Ticket#":"SYNTH-5","Titel":"Synthetisch","Typ":"Spam","Status":"closed successful", "period":"current","ClosedByID":"61","ResponseByID":"61","ClosedAt":"2026-10-02T10:00:00+02:00","response_minutes":0}]
    cache.update(batch)
    settings=QSettings(str(tmp_path/"test.ini"),QSettings.Format.IniFormat)
    settings.setValue("team_selection",'["61"]')
    page=AgentsPage(cache,settings)
    page.show();qapp.processEvents()
    assert "81" in page.registry and "81" not in page.selected
    assert page.values["Geschlossen"].text()=="1"
    assert page.values["Median Reaktionszeit"].text()=="0 min"
    assert "Nico Köchli" not in page.table.model().frame.to_string()
    assert metrics(batch,{"61"})[0]["Geschlossen"]==1
    page.close()
    restarted=AgentsPage(cache,settings)
    assert restarted.selected=={"61"}
    restarted.close()
