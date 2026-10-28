"""Summarize source-app trials; preserve raw logs and unsuccessful runs."""

from collections import Counter
import json
from pathlib import Path
import shutil
import statistics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/mc-b1-05r-20261028"
RUNTIME = ROOT / "artifacts/minecraft-chat"
all_events = [
    json.loads(line) for line in (RUNTIME / "events.jsonl").read_text().splitlines()
]
start = min(json.loads(p.read_text())["started"] for p in OUT.glob("trial-*.json")) * 1000
events = [e for e in all_events if e["at_ms"] >= start]
workers = [
    json.loads(line)
    for line in (RUNTIME / "worker-events.jsonl").read_text().splitlines()
]
workers = [e for e in workers if e["at_ms"] >= start]
for name, rows in [("events", events), ("worker-events", workers)]:
    (OUT / (name + ".jsonl")).write_text("".join(json.dumps(e) + "\n" for e in rows))
for name in ("conversation.json", "places.json", "construction.json", "memory.json"):
    if (RUNTIME / name).exists():
        shutil.copy2(RUNTIME / name, OUT / name)
returned = [e for e in events if e["kind"] == "inference_returned"]
usage = [u for e in returned for u in e.get("usage", [])]
tokens = Counter()
for u in usage:
    tokens.update(u.get("tokens") or {})
latencies = [u["seconds"] for u in usage]
goals = []
for e in events:
    if e["kind"] != "goal_started":
        continue
    gid = e["goal_id"]
    req = next(
        r
        for r in reversed(events)
        if r["kind"] == "message" and r["at_ms"] <= e["at_ms"]
    )
    children = [
        r for r in events if r.get("goal_id") == gid and r["kind"] == "goal_child"
    ]
    outcomes = [
        r for r in events if r.get("goal_id") == gid and r["kind"].endswith("_outcome")
    ]
    results = [
        r
        for r in events
        if r.get("goal_id") == gid and r["kind"] == "goal_child_result"
    ]
    physical = [
        r
        for r in results
        if r["result"].get("observed")
        in {"position", "server_placement", "server_block_change", "inventory_delta"}
    ]
    goals.append(
        {
            "goal_id": gid,
            "request": req["text"],
            "first_child_submission_seconds": (children[0]["at_ms"] - req["at_ms"])
            / 1000
            if children
            else None,
            "first_verified_physical_result_seconds": (
                physical[0]["at_ms"] - req["at_ms"]
            )
            / 1000
            if physical
            else None,
            "full_seconds": (outcomes[-1]["at_ms"] - req["at_ms"]) / 1000
            if outcomes
            else None,
            "recoveries": sum(
                r["kind"] == "goal_recovery" and r.get("goal_id") == gid for r in events
            ),
            "skills": dict(Counter(c["action"]["action"] for c in children)),
            "outcome": outcomes[-1] if outcomes else None,
        }
    )
stops = []
for e in events:
    if e["kind"] != "stop_requested":
        continue
    end = next(
        (
            r
            for r in events
            if r["kind"] == "stop_completed" and r["at_ms"] >= e["at_ms"]
        ),
        None,
    )
    nxt = next(
        (
            r["at_ms"]
            for r in events
            if r["kind"] == "message" and r["at_ms"] > e["at_ms"]
        ),
        float("inf"),
    )
    dispatch = next(
        (
            r
            for r in workers
            if r["type"] == "cancel_dispatched"
            and e["at_ms"] - 2 <= r["at_ms"]
            and (not end or r["at_ms"] <= end["at_ms"])
        ),
        None,
    )
    stops.append(
        {
            "at_ms": e["at_ms"],
            "dispatch_ms": max(0, dispatch["at_ms"] - e["at_ms"]) if dispatch else None,
            "observed_cessation_ms": end["at_ms"] - e["at_ms"] if end else None,
            "result": end.get("result") if end else None,
            "children_before_next_intent": sum(
                r["kind"] == "goal_child" and e["at_ms"] < r["at_ms"] < nxt
                for r in events
            ),
        }
    )
phases = []
for path in OUT.glob("sustained*-start.json"):
    endpath = path.with_name(path.name.replace("-start", "-extended-end"))
    if not endpath.exists():
        endpath = path.with_name(path.name.replace("-start", "-end"))
    if not endpath.exists():
        continue
    begin = json.loads(path.read_text())
    end = json.loads(endpath.read_text())
    if "at" not in begin or "at" not in end:
        continue
    a, b = begin["at"] * 1000, end["at"] * 1000
    samples = [r for r in workers if r["type"] == "state" and a <= r["at_ms"] <= b]
    active = sum(
        min(2, max(0, (samples[i + 1]["at_ms"] - r["at_ms"]) / 1000))
        for i, r in enumerate(samples[:-1])
        if r.get("result", {}).get("active")
    )
    durations = [
        u["seconds"]
        for r in returned
        if a <= r["at_ms"] <= b
        for u in r.get("usage", [])
    ]
    timeline = [(a, "work", 0), (b, "work", 0)]
    for i, sample in enumerate(samples[:-1]):
        if sample.get("result", {}).get("active"):
            timeline.extend(
                [
                    (sample["at_ms"], "work", 1),
                    (min(sample["at_ms"] + 2000, samples[i + 1]["at_ms"]), "work", -1),
                ]
            )
    for reply in returned:
        if not a <= reply["at_ms"] <= b:
            continue
        began = next(
            (
                r
                for r in reversed(events)
                if r["kind"] == "inference_started"
                and r.get("role") == reply.get("role")
                and r.get("authority") == reply.get("authority")
                and a <= r["at_ms"] <= reply["at_ms"]
            ),
            None,
        )
        if began:
            timeline.extend(
                [(began["at_ms"], "model", 1), (reply["at_ms"], "model", -1)]
            )
    running = Counter()
    timing = Counter()
    previous = a
    for when, kind, delta in sorted(timeline):
        label = (
            "work_during_reasoning"
            if running["work"] and running["model"]
            else "work_without_reasoning"
            if running["work"]
            else "reasoning_without_worker_activity"
            if running["model"]
            else "conversation_transition_or_operator_gap"
        )
        timing[label] += (when - previous) / 1000
        running[kind] += delta
        previous = when
    phases.append(
        {
            "phase": path.stem,
            "elapsed_seconds": (b - a) / 1000,
            "sampled_worker_active_seconds": active,
            "returned_model_seconds": sum(durations),
            "estimated_time_breakdown_seconds": dict(timing),
            "note": "Worker activity and inference may overlap. Remaining elapsed time includes conversation, transitions, observation and operator gaps; it is not claimed as physical work.",
        }
    )
summary = {
    "goals": goals,
    "returned_calls": len(returned),
    "reported_tokens": dict(tokens),
    "latency_seconds": {
        "min": min(latencies) if latencies else None,
        "median": statistics.median(latencies) if latencies else None,
        "max": max(latencies) if latencies else None,
        "normal_at_most_10": [x for x in latencies if x <= 10],
        "slow_over_10": [x for x in latencies if x > 10],
    },
    "started_without_returned_result": sum(
        e["kind"] == "inference_started" for e in events
    )
    - len(returned),
    "unreported_call_usage": "unknown, not zero",
    "stops": stops,
    "phases": phases,
    "physical_timing_note": "First verified result is an upper bound for first physical action, not an exact onset timestamp.",
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2))
print(
    json.dumps(
        {k: v for k, v in summary.items() if k not in {"goals", "latency_seconds"}},
        indent=2,
    )
)
