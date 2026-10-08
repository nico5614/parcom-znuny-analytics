from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from time import sleep

import pytest
import requests

from parcom_analytics.znuny import ConnectionError, SessionExpired, ZnunyClient, ZnunyError
from performance_benchmark import BenchmarkTransport, Response


def connected(transport, concurrency=4):
    client = ZnunyClient(transport, concurrency=concurrency)
    client._session_id = "synthetic-session"
    return client


@pytest.mark.parametrize("limit", [1, 4])
def test_parallel_limit_order_duplicates_and_zero_values(limit):
    transport = BenchmarkTransport(latency=.03)
    client = connected(transport, limit)
    ids = list(map(str, range(1, 17))) + ["1"]
    result = client.get_tickets(ids)
    assert [item["TicketID"] for item in result] == ids
    assert all(item["FirstResponseInMin"] == 0 for item in result)
    assert transport.maximum == limit
    assert transport.calls["TicketGet"]["count"] == 16


def test_bound_is_shared_across_simultaneous_consumers():
    transport = BenchmarkTransport(latency=.03)
    client = connected(transport)
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(client.get_tickets, range(i, i+12)) for i in (1, 20, 40)]
        assert all(len(job.result()) == 12 for job in jobs)
    assert transport.maximum == 4


@pytest.mark.parametrize("operation", ["get_ticket", "get_history"])
def test_inflight_deduplication_and_mutation_isolation(operation):
    transport = BenchmarkTransport(latency=.08)
    client = connected(transport)
    start = Barrier(5)

    def fetch():
        start.wait(timeout=2)
        return getattr(client, operation)("1")

    with ThreadPoolExecutor(max_workers=5) as pool:
        values = list(pool.map(lambda _: fetch(), range(5)))
    name = "TicketGet" if operation == "get_ticket" else "TicketHistory"
    assert transport.calls[name]["count"] == 1
    assert values[0] is not values[1]
    assert client._inflight == {}


@pytest.mark.parametrize("failure", [requests.Timeout("private"), SessionExpired("expired")])
def test_parallel_failure_is_atomic_and_can_retry(failure):
    transport = BenchmarkTransport(latency=.02)
    original = transport.request

    def fail(method, url, **kwargs):
        if url.endswith("/1"):
            raise failure
        return original(method, url, **kwargs)

    transport.request = fail
    client = connected(transport)
    expected = ConnectionError if isinstance(failure, requests.Timeout) else SessionExpired
    with pytest.raises(expected):
        client.get_tickets(range(1, 41))
    assert not client._inflight
    assert transport.calls.get("TicketGet", {}).get("count", 0) <= 3
    transport.request = original
    assert len(client.get_tickets([1, 2])) == 2


def test_parallel_auth_failure_cannot_be_overwritten_by_success():
    transport = BenchmarkTransport(latency=.04)
    original = transport.request

    def request(method, url, **kwargs):
        if url.endswith("/1"):
            sleep(.01)
            response = Response({})
            response.status_code = 401
            return response
        return original(method, url, **kwargs)

    transport.request = request
    client = connected(transport)
    with pytest.raises(SessionExpired):
        client.get_tickets(range(1, 20))
    assert client._session_id is None and not client.connected


def test_cancellation_does_not_publish_partial_batch():
    transport = BenchmarkTransport(latency=.01)
    client = connected(transport)
    cancel = Event()
    cancel.set()
    with pytest.raises(ZnunyError, match="abgebrochen"):
        client.get_tickets(range(1, 20), cancel)
    assert not transport.calls


def test_persistent_sessions_are_bounded_and_verify_tls():
    client = ZnunyClient()
    sessions = list(client._sessions.queue)
    assert len({id(session) for session in sessions}) == 4
    for session in sessions:
        adapter = session.get_adapter("https://znuny.parcom.ch")
        assert session.verify is True and session.trust_env is False
        assert adapter._pool_maxsize == 1 and adapter._pool_block


def test_timings_contain_only_safe_operation_aggregates():
    transport = BenchmarkTransport(latency=0)
    client = connected(transport)
    client.get_ticket("1")
    stats = client.timings.snapshot()
    assert stats["TicketGet"]["count"] == 1
    assert stats["TicketGet"]["failures"] == 0
    assert set(stats["TicketGet"]) == {"count", "seconds", "failures", "average_seconds"}
    assert "synthetic" not in repr(stats)


def test_injected_requests_session_is_never_used_concurrently():
    transport = BenchmarkTransport(latency=.01)
    session = requests.Session()
    session.request = transport.request
    client = connected(session)
    assert len(client.get_tickets(range(1, 9))) == 8
    assert transport.maximum == 1
    client.logout()
