"""Eight-call causal matrix: only surrounding source-question context varies.

Recorded observations, exact retained evidence inventory and model settings stay
fixed. Expected labels are review data, never sent to the model. No world opens.
"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading
import time

from smb3_agent.ai_provider import create_provider
from smb3_agent.minecraft_grounding import (
    question_context,
    selection_schema,
    compose_answer,
    QuestionDeadline,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    retained_path = Path("artifacts/sustained-metrics/grounding-decomposition03.json")
    retained = json.loads(retained_path.read_text())["answers"][1]
    log = Path(
        "artifacts/sustained-ordinary12/profile/artifacts/minecraft-chat/worker-events.jsonl"
    )
    state = next(
        json.loads(line)["result"]
        for line in log.open()
        if json.loads(line).get("type") == "state"
    )
    context = question_context(
        {
            "request": retained["question"],
            "project": retained["supplied_project"],
            "observations": state,
        }
    )
    # Recover the exact pre-edit shared procedure text from this retained trial.
    # This is an in-memory diagnostic inventory, not a production fact change.
    context["evidence"]["change_dimensions"]["text"] = context["evidence"][
        "change_dimensions"
    ]["text"].replace(
        "To change reviewed dimensions: (1) Stop active companion work; (2) edit the intended width, depth or height in the design;",
        "For a taller building, change height, not base elevation. To change any reviewed dimensions: (1) Stop active companion work; (2) edit the design;",
    )
    # The retained wording did not contain "any"; keep its exact byte identity.
    context["evidence"]["change_dimensions"]["text"] = context["evidence"][
        "change_dimensions"
    ]["text"].replace(
        "To change any reviewed dimensions:", "To change reviewed dimensions:"
    )
    snapshot = hashlib.sha256(
        json.dumps(context["evidence"], sort_keys=True).encode()
    ).hexdigest()
    assert snapshot == retained["interpretation"]["snapshot_id"], (
        "Retained evidence inventory reconstruction differs"
    )
    original_span = retained["interpretation"]["source_spans"][1]
    original = {
        **context,
        "request": original_span["text"],
        "question_stage": "select_span",
        "source_question": retained["question"],
        "source_span": original_span,
        "snapshot_id": snapshot,
    }
    ordered = {k: v for k, v in original.items() if k != "request"} | {
        "request": original["request"]
    }
    assert (
        len(json.dumps(ordered, allow_nan=False))
        == retained["usage"][-1]["context_chars"]
    ), "Retained envelope size differs"
    matrix = [
        {
            "id": "original_surrounding",
            "expected": ["reopening"],
            "mode": "surrounding",
            "context": original,
            "retained_selection": retained["interpretation"]["coverage"][1][
                "selection"
            ],
            "retained_usage": retained["usage"][-1],
            "actual_call": False,
        }
    ]
    isolated = deepcopy(original)
    isolated.pop("source_question")
    matrix.append(
        {
            "id": "original_isolated",
            "expected": ["reopening"],
            "mode": "isolated",
            "context": isolated,
            "actual_call": True,
        }
    )
    variants = [
        (
            "unseen_forward",
            "Do receipts describe earlier work, and will loading the same saved world delete its buildings?",
            "and will loading the same saved world delete its buildings?",
        ),
        (
            "reversed",
            "Does reopening erase the existing world, and what does our old receipt count mean?",
            "Does reopening erase the existing world, ",
        ),
        (
            "unseen_reversed",
            "Will my buildings stay when I reopen, and are receipt totals historical?",
            "Will my buildings stay when I reopen, ",
        ),
    ]
    for name, full, target in variants:
        start = full.index(target)
        span = {
            "index": 1 if start else 0,
            "start": start,
            "end": start + len(target),
            "text": target,
        }
        surrounding = {
            **context,
            "request": target,
            "question_stage": "select_span",
            "source_question": full,
            "source_span": span,
            "snapshot_id": snapshot,
        }
        for mode in ("surrounding", "isolated"):
            envelope = deepcopy(surrounding)
            if mode == "isolated":
                envelope.pop("source_question")
            matrix.append(
                {
                    "id": name + "_" + mode,
                    "expected": ["reopening"],
                    "mode": mode,
                    "context": envelope,
                    "actual_call": True,
                }
            )
    control = deepcopy(original)
    control.pop("source_question")
    control["request"] = (
        "Does a completion receipt prove nobody edited the building afterward?"
    )
    control["source_span"] = {
        "index": 0,
        "start": 0,
        "end": len(control["request"]),
        "text": control["request"],
    }
    matrix.append(
        {
            "id": "history_control",
            "expected": ["historical_records"],
            "mode": "isolated",
            "context": control,
            "actual_call": True,
        }
    )
    assert sum(row["actual_call"] for row in matrix) == 8
    assert all(row["context"]["evidence"] == context["evidence"] for row in matrix)
    report = {
        "scope": "Eight-call context ablation; retained original compound result reused, not rerun",
        "retained_inventory_digest_verified": snapshot,
        "retained_context_chars_verified": len(json.dumps(ordered)),
        "original_http_body_was_not_retained": True,
        "matrix": matrix,
        "answers": [],
        "limits": {
            "actual_calls": 8,
            "aggregate_seconds": 600,
            "call_seconds": 240,
            "generated_tokens_per_call": 512,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        tmp = args.output.with_suffix(".tmp")
        tmp.write_text(json.dumps(report, indent=2))
        tmp.replace(args.output)

    save()  # Predeclare every case before the first call; expected labels are not inputs.
    provider = create_provider()
    until = time.monotonic() + 600
    try:
        with provider._discovery_lock:
            assert provider.status["available"]
        for case in matrix:
            row = {"id": case["id"]}
            if not case["actual_call"]:
                row.update(
                    {
                        "selection": case["retained_selection"],
                        "reused": True,
                        "usage": [case["retained_usage"]],
                    }
                )
                report["answers"].append(row)
                save()
                continue
            if time.monotonic() >= until:
                raise TimeoutError("Aggregate diagnostic deadline")
            started, usage_start = time.monotonic(), len(provider.usage)
            report["answers"].append(row)
            try:
                selection = provider.infer(
                    "language",
                    case["context"],
                    selection_schema(context),
                    QuestionDeadline(
                        threading.Event(), min(240, until - time.monotonic())
                    ),
                )
                row["selection"] = selection
                row["composed"] = compose_answer(case["context"], selection)
            except Exception as exc:
                row["error"] = str(exc)
            row["seconds"] = time.monotonic() - started
            row["usage"] = provider.usage[usage_start:]
            save()
            print(json.dumps(row), flush=True)
    finally:
        provider.close()
        report["closed"] = True
        report["actual_calls"] = len(provider.usage)
        save()


if __name__ == "__main__":
    main()
