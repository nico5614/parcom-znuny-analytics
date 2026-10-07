from datetime import date
from threading import Event
from unittest.mock import Mock

import pandas as pd
import pytest
import requests

from parcom_analytics.analytics import DataError
from parcom_analytics.live_data import DateRange, fetch_live, normalize_tickets
from parcom_analytics.znuny import (BASE_URL, DEFAULT_QUEUES, ConnectionError, LoginError,
                                   SessionExpired, ZnunyClient, ZnunyError)


def response(payload, status=200):
    return Mock(status_code=status, json=Mock(return_value=payload))


@pytest.fixture
def client():
    transport = Mock()
    transport.request.return_value = response({"SessionID": "synthetic-session"})
    instance = ZnunyClient(transport)
    instance.login("synthetic-user", "synthetic-password")
    return instance


def test_login_and_readonly_transport(client, caplog):
    assert client.connected
    args, kwargs = client._http.request.call_args
    assert args == ("POST", BASE_URL + "/Session")
    assert kwargs["verify"] is True and kwargs["allow_redirects"] is False
    assert kwargs["timeout"] == (5, 30)
    assert "synthetic-password" not in repr(vars(client))
    assert "synthetic-session" not in caplog.text
    with pytest.raises(KeyError):
        client._request("TicketUpdate")


@pytest.mark.parametrize("payload,status", [({"Error": {"ErrorCode": "SessionCreate.AuthFail"}}, 200), ({}, 401), ({}, 200)])
def test_login_failure(payload, status):
    transport = Mock(request=Mock(return_value=response(payload, status)))
    with pytest.raises(LoginError, match="Benutzername oder Passwort"):
        ZnunyClient(transport).login("user", "secret")


@pytest.mark.parametrize("failure", [requests.Timeout("secret"), requests.ConnectionError("secret")])
def test_network_failure_is_sanitized(client, failure, caplog):
    client._http.request.side_effect = failure
    with pytest.raises(ConnectionError, match="Keine Verbindung") as caught:
        client.test_connection()
    assert "secret" not in str(caught.value) + caplog.text
    assert not client.connected


def test_session_expiration(client):
    client._http.request.return_value = response({"Error": {"ErrorCode": "TicketGet.AuthFail"}})
    with pytest.raises(SessionExpired):
        client.get_ticket(1)
    assert client._session_id is None and not client.connected


@pytest.mark.parametrize("failed", [False, True])
def test_logout_always_discards_session(client, failed):
    if failed:
        client._http.request.side_effect = requests.Timeout()
    client.logout()
    args, kwargs = client._http.request.call_args
    assert args == ("DELETE", BASE_URL + "/Session/synthetic-session")
    assert kwargs["timeout"] == (1, 2)
    assert client._session_id is None and not client.connected
    calls = client._http.request.call_count
    client.logout()
    assert client._http.request.call_count == calls


@pytest.mark.parametrize("payload,expected", [({"TicketID": [1, 2]}, ["1", "2"]), ({"TicketIDs": [3]}, ["3"]), ({}, []), ({"TicketID": "4"}, ["4"])])
def test_search_shapes_queues_and_connection(client, payload, expected):
    client._http.request.return_value = response(payload)
    assert client.search_tickets() == expected
    args, kwargs = client._http.request.call_args
    assert args == ("POST", BASE_URL + "/Ticket/Search")
    assert kwargs["json"]["Queues"] == list(DEFAULT_QUEUES)
    assert client.connected


def test_ticket_get_uses_single_ticket_route_and_requires_matching_id(client):
    client._http.request.return_value = response({"Ticket": [{"TicketID": 1, "FirstResponseInMin": 0}]})
    assert client.get_ticket(1)["FirstResponseInMin"] == 0
    args, kwargs = client._http.request.call_args
    assert args == ("GET", BASE_URL + "/Ticket/1")
    params = kwargs["params"]
    assert params["Extended"] == 1 and params["AllArticles"] == params["Attachments"] == 0
    client._http.request.return_value = response({"Ticket": [{"TicketID": 2}]})
    with pytest.raises(ZnunyError):
        client.get_ticket(1)


def test_ticket_get_multiple_ids_calls_single_ticket_route_per_id(client):
    client._http.request.reset_mock()
    client._http.request.side_effect = [response({"Ticket": [{"TicketID": 1}]}),
                                        response({"Ticket": [{"TicketID": 2}]})]
    assert [item["TicketID"] for item in client.get_tickets([1, 2])] == [1, 2]
    assert [call.args[:2] for call in client._http.request.call_args_list] == [
        ("GET", BASE_URL + "/Ticket/1"), ("GET", BASE_URL + "/Ticket/2")]


def test_normalized_fields_missing_zero_and_privacy():
    frame = normalize_tickets([{"TicketNumber": "001", "Age": 3660, "FirstResponseInMin": 0,
                                "CustomerID": "do-not-store", "Article": [{"Body": "private"}]}])
    assert frame.iloc[0]["Ticket#"] == "001"
    assert frame.iloc[0]["Alter"] == "61 m"
    assert frame.iloc[0]["Erstantwortzeit in Minuten"] == 0
    assert pd.isna(frame.iloc[0]["Lösungszeit in Minuten"])
    assert pd.isna(frame.iloc[0]["FirstResponseTimeEscalation"])
    assert "CustomerID" not in frame and "Article" not in frame


@pytest.mark.parametrize("preset,days", [("7d", 7), ("30d", 30), ("3m", 92), ("6m", 183), ("12m", 365)])
def test_period_presets(preset, days):
    period = DateRange.preset(preset, date(2026, 9, 30))
    assert (period.end-period.start).days + 1 == days


@pytest.mark.parametrize("start,end", [(date(2025, 9, 30), date(2026, 9, 30)), (date(2026, 9, 30), date(2026, 9, 1))])
def test_invalid_period(start, end):
    with pytest.raises(DataError):
        DateRange(start, end)


def test_fetch_distinguishes_snapshot_and_monthly_searches():
    client = Mock()
    client.search_tickets.side_effect = [["1"], ["2"], ["3"], ["3"]]
    client.get_tickets.return_value = [{"TicketID": value, "Queue": "PBX"} for value in ("1", "2", "3")]
    batch = fetch_live(client, DateRange.preset("30d", date(2026, 9, 30)), Event())
    assert set(batch.frames) == set(range(1, 8))
    calls = client.search_tickets.call_args_list
    assert "TicketCreateTimeNewerDate" in calls[0].args[0]
    assert "TicketCloseTimeNewerDate" in calls[1].args[0]
    assert not any("Time" in key for call in calls[2:] for key in call.args[0])
    assert batch.frames[7]["TicketID"].tolist() == ["3"]
