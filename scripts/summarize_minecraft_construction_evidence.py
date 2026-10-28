"""Summarize retained ordinary-app evidence without rewriting source logs."""

from collections import Counter
import json
from pathlib import Path
import shutil
import statistics

ROOT = Path(__file__).resolve().parents[1]
runtime = ROOT / "artifacts/minecraft-chat"
out = ROOT / "artifacts/mc-b1-04-live-20261028"
out.mkdir(exist_ok=True)
all_events = [
    json.loads(line) for line in (runtime / "events.jsonl").read_text().splitlines()
]
start = next(
    e["at_ms"]
    for e in all_events
    if e.get("kind") == "message"
    and e.get("text")
    == "Gather what you need and build a small oak shelter near camp, with a doorway facing me."
)
events = [e for e in all_events if e["at_ms"] >= start]
(out / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
workers = [
    json.loads(line)
    for line in (runtime / "worker-events.jsonl").read_text().splitlines()
]
workers = [e for e in workers if e["at_ms"] >= start]
(out / "worker-events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in workers))
for name in ("conversation.json", "places.json", "construction.json"):
    if (runtime / name).exists():
        shutil.copy2(runtime / name, out / name)
goals = []
for begin in [e for e in events if e["kind"] == "goal_started"]:
    gid = begin["goal_id"]
    children = [
        e for e in events if e.get("goal_id") == gid and e["kind"] == "goal_child"
    ]
    results = [
        e
        for e in events
        if e.get("goal_id") == gid and e["kind"] == "goal_child_result"
    ]
    outcomes = [
        e
        for e in events
        if e.get("goal_id") == gid
        and e["kind"] in ("construction_outcome", "craft_outcome", "goal_outcome")
    ]
    request = next(
        e
        for e in reversed(events)
        if e["kind"] == "message" and e["at_ms"] <= begin["at_ms"]
    )
    outcome = outcomes[-1] if outcomes else None
    goals.append(
        {
            "goal_id": gid,
            "request": request["text"],
            "action": begin["plan"]["action"],
            "first_child_seconds": round(
                (children[0]["at_ms"] - request["at_ms"]) / 1000, 3
            )
            if children
            else None,
            "full_seconds": round((outcome["at_ms"] - request["at_ms"]) / 1000, 3)
            if outcome
            else None,
            "skills": dict(Counter(c["action"]["action"] for c in children)),
            "verified_placements": sum(
                r["result"].get("observed") == "server_placement" for r in results
            ),
            "verified_breaks": sum(
                r["result"].get("observed") == "server_block_change" for r in results
            ),
            "recoveries": sum(
                e.get("goal_id") == gid and e["kind"] == "goal_recovery" for e in events
            ),
            "outcome": outcome,
        }
    )
returned = [e for e in events if e["kind"] == "inference_returned"]
usage = [u for e in returned for u in e.get("usage", [])]
seconds = [u["seconds"] for u in usage]
tokens = Counter()
for u in usage:
    tokens.update(u.get("tokens") or {})
stops = []
for stop in [e for e in events if e["kind"] == "stop_requested"]:
    end = next(
        (
            e
            for e in events
            if e["kind"] == "stop_completed" and e["at_ms"] >= stop["at_ms"]
        ),
        None,
    )
    next_request = next(
        (
            e["at_ms"]
            for e in events
            if e["kind"] == "message" and e["at_ms"] > stop["at_ms"]
        ),
        float("inf"),
    )
    dispatch = next(
        (
            e
            for e in workers
            if e["type"] == "cancel_dispatched"
            and e["at_ms"] >= stop["at_ms"] - 20
            and (end is None or e["at_ms"] <= end["at_ms"])
        ),
        None,
    )
    stops.append(
        {
            "requested_at_ms": stop["at_ms"],
            "dispatch_ms": round(max(0, dispatch["at_ms"] - stop["at_ms"]), 3)
            if dispatch
            else None,
            "cessation_ms": round(end["at_ms"] - stop["at_ms"], 3) if end else None,
            "confirmation": end.get("result") if end else None,
            "children_until_next_request": sum(
                e["kind"] == "goal_child" and stop["at_ms"] < e["at_ms"] < next_request
                for e in events
            ),
        }
    )
summary = {
    "goals": goals,
    "returned_calls": len(returned),
    "latency_seconds": {
        "min": min(seconds),
        "median": statistics.median(seconds),
        "max": max(seconds),
    },
    "reported_tokens": dict(tokens),
    "unreturned_started_calls": len(
        [e for e in events if e["kind"] == "inference_started"]
    )
    - len(returned),
    "unreturned_usage": "unknown, not zero",
    "stops": stops,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2))
print(json.dumps({k: v for k, v in summary.items() if k != "goals"}, indent=2))
