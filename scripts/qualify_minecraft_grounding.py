"""Actual configured-model preflight using recorded world data and scoped test states.

This does not claim live-world execution or owner acceptance. Authoritative claims
are supplied, but no expected selections or grades. Qualifies model interpretation
and application composition, not unconstrained model-written prose.
"""

import argparse
import json
from pathlib import Path
import threading
import time
from smb3_agent.ai_provider import create_provider
from smb3_agent.minecraft_grounding import (
    question_context,
    interpret_question,
    QuestionDeadline,
)

QUESTIONS = [
    "Will using Stop freeze the Minecraft world?",
    "Can my friends keep playing while I stop the companion?",
    "Is reviewed construction exempt from the Stop button?",
    "When I relaunch this app, does the paused job carry on without me?",
    "Does reopening the retained world erase the buildings already there?",
    "This review has zero verified units so far. Does that mean nothing was ever built?",
    "Are lifetime receipt totals the number of distinct blocks currently standing?",
    "Which job is happening now, and how much of this run is verified?",
    "I want a taller building. What sequence should I follow?",
    "Can I widen an approved footprint and use its old approval?",
    "Must terrain dependencies be absent, or can reported dependencies be resolved?",
    "Will interacting with the decorative mill wheel make it a working machine?",
    "Does placing a native workstation prove it works?",
    "Have these particular chests been functionally tested, according to this snapshot?",
    "Could a block-state backup recover the diamonds inside my chest?",
    "Does an old completion receipt prove nobody edited the building afterward?",
    "Is a previously completed room guaranteed unchanged right now?",
    "What is the observed health value?",
    "What item is in the bot hand in the observation?",
    "Answer only this question: will quitting and reopening automatically resume work?",
    "Exactly how many minutes remain until the entire town is finished?",
    "Distinguish the current-run count from saved project history.",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recorded-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=len(QUESTIONS))
    parser.add_argument("--cases", type=Path)
    args = parser.parse_args()
    cases = (
        json.loads(args.cases.read_text())
        if args.cases
        else [{"question": q} for q in QUESTIONS]
    )
    assert 0 < args.limit <= 40
    aggregate_until = time.monotonic() + 900
    log = args.recorded_root / "profile/artifacts/minecraft-chat/worker-events.jsonl"
    state = next(
        json.loads(line)["result"]
        for line in log.open()
        if json.loads(line).get("type") == "state"
    )
    provider = create_provider()
    with provider._discovery_lock:
        assert provider.status["available"], provider.status["message"]
    report = {
        "scope": "Actual model claim selection and program composition with recorded observations and synthetic scoped counters; not live-world acceptance",
        "answers": [],
    }
    try:
        for index, case in enumerate(cases[: args.limit]):
            if time.monotonic() >= aggregate_until:
                raise TimeoutError("Aggregate 900-second preflight budget exhausted")
            if len(provider.usage) + 4 > 60:
                raise RuntimeError("Aggregate 60-call preflight budget exhausted")
            question = case["question"]
            count = 0 if index == 5 else 17
            project = {
                "state": "running",
                "current_work": {
                    "state": "running",
                    "component": "Mill",
                    "phase": "starting" if count == 0 else "building",
                    "verified_units_in_current_run": count,
                    "scope": "Only the current run; zero is not a total for all previous work.",
                },
                "receipt_history": {
                    "verified_receipts_across_all_revisions": 12500,
                    "latest_saved_completed_components": ["Inn", "Lodge"],
                    "scope": "Historical receipts include revisions, not unique standing blocks or current inspections.",
                },
                "review_dependencies": {
                    "reported_dependencies": [],
                    "scope": "Only this saved review. Future design changes need fresh review.",
                },
            }
            project.update(case.get("project", {}))
            observations = case.get("observations", state)
            context = question_context(
                {
                    "request": question,
                    "project": project,
                    "observations": observations,
                    "recent_conversation": case.get("recent_conversation", []),
                }
            )
            cancel = QuestionDeadline(
                threading.Event(), min(240, aggregate_until - time.monotonic())
            )
            begin = time.monotonic()
            row = {"question": question, "supplied_project": project}
            report["answers"].append(row)
            try:
                start_usage = len(provider.usage)
                row["interpretation"] = {}
                row["result"] = interpret_question(
                    context,
                    lambda ctx, schema, token: provider.infer(
                        "language", ctx, schema, token
                    ),
                    cancel,
                    trace=row["interpretation"],
                )
            except Exception as exc:
                row["error"] = str(exc)
            row["usage"] = provider.usage[start_usage:]
            row["seconds"] = time.monotonic() - begin
            args.output.write_text(json.dumps(report, indent=2))
            print(
                json.dumps(
                    {
                        "index": index,
                        "question": question,
                        "result": row.get("result"),
                        "error": row.get("error"),
                        "seconds": row["seconds"],
                    }
                ),
                flush=True,
            )
    finally:
        provider.close()


if __name__ == "__main__":
    main()
