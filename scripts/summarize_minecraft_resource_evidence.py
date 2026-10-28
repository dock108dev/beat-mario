"""Retain and summarize the source-app event evidence, including failures."""

import json
from pathlib import Path
import shutil
import statistics

root = Path(__file__).resolve().parents[1]
out = root / "artifacts/mc-b1-03-live-20261027"
out.mkdir(exist_ok=True)
runtime = root / "artifacts/minecraft-chat"
all_events = [
    json.loads(s) for s in (runtime / "events.jsonl").read_text().splitlines()
]
start = next(
    e["at_ms"]
    for e in all_events
    if e["kind"] == "connected" and e["state"].get("world_id")
)
events = [e for e in all_events if e["at_ms"] >= start]
worker = [
    json.loads(s) for s in (runtime / "worker-events.jsonl").read_text().splitlines()
]
worker = [e for e in worker if e["at_ms"] >= start]
for name, rows in (("events.jsonl", events), ("worker-events.jsonl", worker)):
    (out / name).write_text("".join(json.dumps(e) + "\n" for e in rows))
for name in ("conversation.json", "places.json"):
    shutil.copy2(runtime / name, out / name)
returned = [e for e in events if e["kind"] == "inference_returned"]
usage = [e["usage"][-1] for e in returned]
latency = [u["seconds"] for u in usage]
goals = []
for e in events:
    if e["kind"] != "goal_started":
        continue
    children = [
        c for c in events if c["kind"] == "goal_child" and c["goal_id"] == e["goal_id"]
    ]
    outcome = next(
        (
            c
            for c in events
            if c["kind"] == "goal_outcome" and c["goal_id"] == e["goal_id"]
        ),
        None,
    )
    message = next(
        m
        for m in reversed(events)
        if m["kind"] == "message" and m["at_ms"] < e["at_ms"]
    )
    states = [
        w["result"]
        for w in worker
        if w["type"] == "state"
        and w["session_id"] == e["authority"][1]
        and w["at_ms"] <= e["at_ms"]
    ]
    goal_usage = [
        u["usage"][-1]
        for u in returned
        if message["at_ms"]
        <= u["at_ms"]
        <= (outcome["at_ms"] if outcome else float("inf"))
    ]
    goals.append(
        {
            "returned_calls_in_window": len(goal_usage),
            "reported_tokens_in_window": {
                key: sum(u.get("tokens", {}).get(key, 0) for u in goal_usage)
                for key in ("input_tokens", "cached_input_tokens", "output_tokens")
            },
            "request_to_outcome_seconds": (outcome["at_ms"] - message["at_ms"]) / 1000
            if outcome
            else None,
            "id": e["goal_id"],
            "request": message["text"],
            "plan": e["plan"],
            "start_position": states[-1]["position"] if states else None,
            "first_child_seconds": (children[0]["at_ms"] - message["at_ms"]) / 1000
            if children
            else None,
            "execution_seconds": (outcome["at_ms"] - e["at_ms"]) / 1000
            if outcome
            else None,
            "child_actions": len(children),
            "outcome": outcome,
        }
    )
stop_results = [e for e in events if e["kind"] == "stop_completed"]
concurrency = []
for e in returned:
    if e["proposal"].get("kind") != "question":
        continue
    began = next(
        s
        for s in reversed(events)
        if s["kind"] == "inference_started"
        and s["authority"] == e["authority"]
        and s["at_ms"] < e["at_ms"]
    )
    overlapping = [
        c
        for c in events
        if c["kind"] == "goal_child_result" and began["at_ms"] < c["at_ms"] < e["at_ms"]
    ]
    active = [
        g
        for g in events
        if g["kind"] == "goal_started"
        and g["authority"] == e["authority"]
        and g["at_ms"] < began["at_ms"]
    ]
    if active:
        goal_id = active[-1]["goal_id"]
        ended = next(
            (
                r
                for r in events
                if r["kind"] == "goal_outcome" and r["goal_id"] == goal_id
            ),
            None,
        )
        concurrency.append(
            {
                "reply": e["proposal"]["reply"],
                "began_ms": began["at_ms"],
                "returned_ms": e["at_ms"],
                "goal_id": goal_id,
                "returned_before_goal_end": bool(ended and ended["at_ms"] > e["at_ms"]),
                "child_results_during_inference": len(overlapping),
            }
        )
summary = {
    "since_ms": start,
    "returned_calls": len(returned),
    "started_calls": sum(e["kind"] == "inference_started" for e in events),
    "unreturned_call_usage": "unknown",
    "latency_seconds": {
        "min": min(latency),
        "median": statistics.median(latency),
        "max": max(latency),
    },
    "reported_tokens": {
        key: sum(u.get("tokens", {}).get(key, 0) for u in usage)
        for key in ("input_tokens", "cached_input_tokens", "output_tokens")
    },
    "goals": goals,
    "concurrent_questions": concurrency,
    "stop_results": stop_results,
    "follow_results": [
        e
        for e in events
        if e["kind"] == "action_result"
        and (
            "follow" in str(e["result"])
            or e["result"].get("observed") == "player_tracking"
        )
    ],
}
(out / "summary.json").write_text(json.dumps(summary, indent=2))
print(
    json.dumps(
        {
            k: v
            for k, v in summary.items()
            if k not in {"goals", "follow_results", "stop_results"}
        },
        indent=2,
    )
)
print(
    json.dumps(
        [
            {
                k: g[k]
                for k in (
                    "id",
                    "request",
                    "first_child_seconds",
                    "execution_seconds",
                    "child_actions",
                )
            }
            for g in goals
        ],
        indent=2,
    )
)
