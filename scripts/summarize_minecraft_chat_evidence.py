"""Read-only summary of retained events; never drives gameplay."""

import json
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/mc-b1-02-live-20261027"


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main():
    events = read(OUT / "events.jsonl")
    worker = read(OUT / "worker-events.jsonl")
    concurrency = []
    for i, event in enumerate(events):
        if event["kind"] != "reply" or not event.get("active"):
            continue
        start = next(
            e for e in reversed(events[:i]) if e["kind"] == "inference_started"
        )
        if start.get("active") == event["active"]:
            concurrency.append(
                {
                    "question_started_ms": start["at_ms"],
                    "reply_ms": event["at_ms"],
                    "active_request_id": event["active"],
                    "authority": event["authority"],
                }
            )
    stops = []
    for event in events:
        if event["kind"] != "stop_requested":
            continue
        dispatch = next(
            (
                e
                for e in worker
                if e["type"] == "cancel_dispatched" and e["at_ms"] >= event["at_ms"] - 1
            ),
            None,
        )
        if not dispatch or dispatch["at_ms"] - event["at_ms"] > 2000:
            continue
        completion = next(
            (
                e
                for e in worker
                if e["type"] == "completed"
                and e["request_id"] == dispatch["request_id"]
                and e["session_id"] == dispatch["session_id"]
                and e["at_ms"] >= dispatch["at_ms"]
            ),
            None,
        )
        if completion:
            stops.append(
                {
                    "request_ms": event["at_ms"],
                    "dispatch_ms": max(0, dispatch["at_ms"] - event["at_ms"]),
                    "observed_cessation_ms": completion["at_ms"] - event["at_ms"],
                    "result": completion["result"],
                }
            )
    samples = {}
    for e in events:
        for u in e.get("usage", []):
            samples[u["request_id"]] = u
    for p in ["after-stop-reconnect.json", "final-state.json"]:
        if (OUT / p).exists():
            for u in json.loads((OUT / p).read_text()).get("usage", []):
                samples[u["request_id"]] = u
    returned = [u for u in samples.values() if u["status"] == "returned"]
    latency = [u["seconds"] for u in returned]
    first_actions = []
    for i, e in enumerate(events):
        if e["kind"] == "action_submitted":
            message = next(m for m in reversed(events[:i]) if m["kind"] == "message")
            first_actions.append(
                {
                    "request": message["text"],
                    "seconds": (e["at_ms"] - message["at_ms"]) / 1000,
                }
            )
    movement = [
        e
        for e in events
        if e["kind"] == "action_result" and e["result"].get("observed") == "position"
    ]
    summary = {
        "concurrent_replies": concurrency,
        "stop_measurements": stops,
        "inference": {
            "returned": len(returned),
            "failed_or_canceled": len(samples) - len(returned),
            "min_seconds": min(latency),
            "median_seconds": median(latency),
            "max_seconds": max(latency),
            "tokens": {
                k: sum(u.get("tokens", {}).get(k, 0) for u in returned)
                for k in ["input_tokens", "cached_input_tokens", "output_tokens"]
            },
            "cli_first_event_seconds": [
                u["cli_first_event_seconds"]
                for u in returned
                if "cli_first_event_seconds" in u
            ],
        },
        "first_actions": first_actions,
        "observed_movements": movement,
    }
    assert concurrency and movement and stops
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
