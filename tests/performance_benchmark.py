"""Offline, synthetic-only benchmark. Run from the repository root with Python.

No server access, credentials, articles or customer data. Fixed 20 ms REST latency
isolates round-trip scheduling from variable live server and network conditions.
"""

import json
import argparse
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
from threading import Event, Lock
from time import perf_counter, sleep
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parcom_analytics.live_data import fetch_live, load_history, commit_live
from parcom_analytics.live_metrics import analyze_live
from parcom_analytics.periods import TimeRange, ZURICH
from parcom_analytics.znuny import ZnunyClient


class Response:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class BenchmarkTransport:
    def __init__(self, count=40, latency=.02):
        self.count, self.latency = count, latency
        self.lock = Lock()
        self.calls = {}
        self.active = self.maximum = 0
        self.changed = []

    def request(self, method, url, **kwargs):
        operation = "TicketSearch" if url.endswith("/Search") else "TicketHistory" if "/History/" in url else "TicketGet"
        started = perf_counter()
        with self.lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
        try:
            sleep(self.latency)
            if operation == "TicketSearch":
                filters = kwargs["json"]
                if "TicketLastChangeTimeNewerDate" in filters:
                    ids = self.changed
                elif "TicketCreateTimeNewerDate" in filters:
                    ids = list(map(str, range(1, self.count+1))) if filters["TicketCreateTimeNewerDate"] >= "2026-09-29" else []
                elif "TicketCloseTimeNewerDate" in filters or filters.get("StateType") == "pending reminder" or "TicketEscalationTimeOlderMinutes" in filters:
                    ids = []
                else:
                    ids = list(map(str, range(1, self.count+1)))
                return Response({"TicketIDs": ids})
            ticket_id = url.rsplit("/", 1)[-1]
            if operation == "TicketHistory":
                return Response({"TicketHistory": [{"TicketID": ticket_id, "History": []}]})
            return Response({"Ticket": [{"TicketID": ticket_id, "TicketNumber": ticket_id,
                "Title": "Synthetic benchmark", "Queue": "PBX", "State": "open", "StateType": "open",
                "Created": "2026-10-01 08:00:00", "Changed": "2026-10-01 08:00:00", "Age": 3600,
                "Type": "Unclassified", "FirstResponseInMin": 0, "SolutionInMin": 0,
                "FirstResponseTimeEscalation": 0, "UntilTime": 0, "Lock": "unlock"}]})
        finally:
            with self.lock:
                self.active -= 1
                entry = self.calls.setdefault(operation, {"count": 0, "seconds": 0})
                entry["count"] += 1
                entry["seconds"] += perf_counter()-started

    def reset(self):
        self.calls = {}
        self.maximum = 0


def run(client, transport, period, loader=fetch_live):
    transport.reset()
    started = perf_counter()
    batch = loader(client, period, Event())
    loaded = perf_counter()
    results = {kpi: analyze_live(kpi, frame, period) for kpi, frame in batch.frames.items()}
    finished = perf_counter()
    calls = {key: {**value, "average_seconds": value["seconds"]/value["count"]} for key, value in transport.calls.items()}
    return {"requests": calls, "maximum_concurrency": transport.maximum,
            "load_seconds": loaded-started, "analytics_seconds": finished-loaded,
            "usable_seconds": finished-started,
            "rows": {key: len(frame) for key, frame in batch.frames.items()},
            "metrics": {key: result.metrics for key, result in results.items()},
            "charts": {key: result.chart.to_dict() for key, result in results.items()}}


def baseline_module(name):
    source = subprocess.run(["git", "show", f"5e993d0:parcom_analytics/{name}.py"],
                            check=True, capture_output=True, encoding="utf-8").stdout
    namespace = {"__name__": f"parcom_analytics.benchmark_{name}", "__package__": "parcom_analytics"}
    # dataclasses resolve type annotations through sys.modules.
    from types import ModuleType
    module = ModuleType(namespace["__name__"])
    module.__dict__.update(namespace)
    sys.modules[module.__name__] = module
    exec(compile(source, f"baseline/{name}.py", "exec"), module.__dict__)
    return module


def history_measurement(client, transport, batch):
    transport.reset()
    started = perf_counter()
    batch = load_history(client, batch, Event())
    commit_live(client, batch)
    return {"requests": deepcopy(transport.calls), "seconds": perf_counter()-started,
            "maximum_concurrency": transport.maximum}, batch


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true", help="Run the immutable base's original client and loader")
    parser.add_argument("--output", type=Path, help="Write UTF-8 aggregate results")
    args = parser.parse_args()
    transport = BenchmarkTransport()
    client = baseline_module("znuny").ZnunyClient(transport) if args.baseline else ZnunyClient(transport)
    loader = baseline_module("live_data").fetch_live if args.baseline else fetch_live
    client._session_id = "synthetic-benchmark-session"
    period = TimeRange.preset("1W", datetime(2026, 10, 6, 14, tzinfo=ZURICH))
    output = {"description": "40 synthetic tickets; 20 ms per request; no live server", "full": run(client, transport, period, loader),
              "unchanged": run(client, transport, period, loader)}
    transport.changed = ["1", "2", "3", "4"]
    output["four_changed"] = run(client, transport, period, loader)
    if not args.baseline:
        history_transport = BenchmarkTransport()
        history_client = ZnunyClient(history_transport)
        history_client._session_id = "synthetic-benchmark-session"
        batch = fetch_live(history_client, period, Event())
        output["history_first"], _ = history_measurement(history_client, history_transport, batch)
        batch = fetch_live(history_client, period, Event())
        output["history_unchanged"], _ = history_measurement(history_client, history_transport, batch)
        history_transport.changed = ["1", "2", "3", "4"]
        batch = fetch_live(history_client, period, Event())
        output["history_four_changed"], _ = history_measurement(history_client, history_transport, batch)
    text = json.dumps(output, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)
