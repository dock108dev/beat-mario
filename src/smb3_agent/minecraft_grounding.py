"""Model-selected, application-owned facts with no model-written authority claims.

The model interprets the question by selecting relevant claims. Answer text comes
from these versioned application semantics and captured state, not model prose.
This validates factual composition, not relevance or general model capability.
"""

from copy import deepcopy
import json
import re
import time


def fact(topic, modality, text):
    return {"topic": topic, "modality": modality, "text": text}


APPLICATION_FACTS = {
    "stop_scope": fact(
        "Stopping companion work and other players",
        "always",
        "Stop cancels companion-controlled work, including active reviewed construction. Minecraft and other players keep running.",
    ),
    "reopening": fact(
        "Saving, reopening and resuming",
        "always",
        "Closing saves the retained world. Reopening preserves its blocks and contents and leaves companion work idle. Inspect fresh state, then explicitly continue to resume work.",
    ),
    "historical_records": fact(
        "Whether previous completion proves the current world unchanged",
        "historical_only",
        "Saved completion records describe past results. They do not establish whether anyone edited the world afterward; fresh inspection is required.",
    ),
    "change_dimensions": fact(
        "Procedure for height, width, footprint or base-elevation changes",
        "ordered_procedure",
        "To change reviewed dimensions: (1) Stop active companion work; (2) edit the intended width, depth or height in the design; (3) if footprint or base elevation changes, review terrain dependencies and complete any required terrain work; (4) review architecture again against the current design and completed terrain; (5) resolve reported dependencies, conflicts and unsupported items; (6) explicitly start the new architecture review. Reviewing alone changes no blocks.",
    ),
    "terrain_conditions": fact(
        "When terrain work is required before architecture",
        "conditional",
        "Architecture needs completed reviewed terrain. A changed footprint or base elevation requires a fresh dependency review; additional terrain work is required only where that review identifies it. Resolve reported dependencies rather than assuming none exist.",
    ),
    "decorative_function": fact(
        "Function of static decorative machinery, including wheels",
        "never",
        "Decorative assemblies such as static wheels have no simulated machine function. Interaction or testing cannot turn them into working machines.",
    ),
    "native_function": fact(
        "Native object mechanics versus proof of functional use",
        "conditional",
        "Native doors, chests, beds, crafting tables and lamps use Minecraft mechanics. Placement alone does not verify function; verification requires a successful live interaction or game-state check.",
    ),
    "native_test_evidence": fact(
        "Whether particular native objects were functionally tested",
        "unknown",
        "This snapshot supplies no functional-test results for particular native objects. Whether they were tested, passed or failed is unknown.",
    ),
    "container_recovery": fact(
        "Recovering items inside containers or removing interactive blocks",
        "unsupported",
        "Block-state recovery cannot restore items inside containers. Removal of interactive blocks is refused when content-aware recovery is unavailable.",
    ),
    "count_scope": fact(
        "Current-run progress versus historical receipts or unique standing blocks",
        "scoped",
        "Current-run progress covers only this run; zero does not mean nothing was built before. Historical receipts include revisions and are not a count of distinct blocks currently standing.",
    ),
    "unknown": fact(
        "Questions not answered by supplied facts, including total completion time",
        "unknown",
        "The available state does not establish that answer.",
    ),
}


def question_context(context):
    facts = deepcopy(APPLICATION_FACTS)
    project = context.get("project", {})
    current = project.get("current_work", {})
    state = current.get("state", project.get("state", "unknown"))
    parts = ["Current companion project state: " + str(state) + "."]
    if current.get("component"):
        parts.append("Current component: " + str(current["component"]) + ".")
    if current.get("phase"):
        parts.append("Current phase: " + str(current["phase"]) + ".")
    count = current.get("verified_units_in_current_run")
    parts.append(
        f"This run has {count} verified units."
        if type(count) is int and count >= 0
        else "A verified-unit count for this run is not supplied."
    )
    facts["current_work"] = fact(
        "Current activity and this run progress", "observed_snapshot", " ".join(parts)
    )
    history = project.get("receipt_history", {})
    count = history.get("verified_receipts_across_all_revisions")
    text = (
        f"Saved history contains {count} verified receipts across all revisions."
        if type(count) is int and count >= 0
        else "A cumulative verified-receipt count is not supplied."
    )
    names = history.get("latest_saved_completed_components")
    if isinstance(names, list):
        text += (
            " Latest saved completed components: "
            + (", ".join(str(n) for n in names) or "none recorded")
            + "."
        )
    facts["saved_history"] = fact(
        "Past completed work and cumulative receipt count",
        "historical_only",
        text
        + " These records are not a fresh world inspection or a count of unique standing blocks.",
    )
    dependencies = project.get("review_dependencies", {}).get("reported_dependencies")
    text = (
        (
            "The saved review reports these dependencies: "
            + json.dumps(dependencies)
            + "."
        )
        if dependencies
        else (
            "The saved review reports no dependencies."
            if dependencies == []
            else "No saved dependency review is supplied."
        )
    )
    facts["review_dependencies"] = fact(
        "Dependencies in this saved review",
        "observed_snapshot",
        text
        + " Future design changes need a fresh review; their dependencies are unknown.",
    )
    observation = context.get("observations", {})
    for key, topic in [
        ("health", "Health"),
        ("food", "Food"),
        ("held_item", "Held item"),
        ("inventory", "Inventory"),
        ("position", "Position"),
        ("players", "Players"),
    ]:
        known = key in observation
        value = observation.get(key)
        rendered = (
            "empty hand" if key == "held_item" and value is None else json.dumps(value)
        )
        facts[key] = fact(
            topic + " in the captured observation",
            "observed_snapshot" if known else "unknown",
            f"{topic} in the captured observation: {rendered}."
            if known
            else f"{topic} is not supplied by this observation; it is unknown.",
        )
    return {
        "request": context["request"],
        "project": {"state": state},
        "evidence": facts,
        "reference_context": [
            {"source": "prior_user_message", "text": m["text"]}
            for m in context.get("recent_conversation", [])
            if m.get("role") == "user" and m.get("text") != context["request"]
        ][-2:],
        "question_stage": "select",
        "read_only_question": True,
    }


def selection_schema(context):
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "fact_ids": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {"type": "string", "enum": list(context["evidence"])},
            }
        },
        "required": ["fact_ids"],
    }


def selected_ids(context, selection):
    ids = selection.get("fact_ids")
    if (
        set(selection) != {"fact_ids"}
        or not isinstance(ids, list)
        or not 1 <= len(ids) <= 3
        or any(not isinstance(key, str) for key in ids)
        or len(ids) != len(set(ids))
        or any(key not in context["evidence"] for key in ids)
    ):
        raise ValueError("Invalid question evidence selection")
    if "unknown" in ids and len(ids) != 1:
        raise ValueError("Unknown answer cannot be combined with supported claims")
    return ids


def compose_answer(context, selection):
    """Validate references, preserve complete procedures and explicit modality.

    No question matching, prose replacement or inferred yes/no polarity occurs.
    Irrelevant selection remains a measurable model failure, not a factual pass.
    """
    ids = selected_ids(context, selection)
    claims = [context["evidence"][key] for key in ids]
    return {
        "kind": "unavailable" if ids == ["unknown"] else "question",
        "reply": "\n\n".join(claim["text"] for claim in claims),
    }


class QuestionDeadline:
    """One question deadline; never cancel ongoing game work."""

    def __init__(self, parent, seconds, *, clock=time.monotonic):
        self.parent, self.clock = parent, clock
        self.until = clock() + min(240, seconds)

    def is_set(self):
        return self.parent.is_set() or self.clock() >= self.until

    def wait(self, seconds):
        remaining = max(0, self.until - self.clock())
        self.parent.wait(min(seconds, remaining))
        return self.is_set()


# One split call plus at most three per-span selection calls. Each provider call
# keeps its configured 512-token ceiling; the aggregate deadline never resets.
MAX_QUESTION_CALLS = 4
MAX_QUESTION_GENERATED_TOKENS = 2048


def source_boundaries(request):
    # Generic syntax candidates, never topic/answer matching. Preserve every
    # character; the model may keep connected noun phrases together by not cutting.
    positions = set()
    for match in re.finditer(r"[?,;\n]\s+|\b(?:and|but|or|also)\s+", request, re.I):
        position = match.end() if re.match(r"[?,;\n]", match.group()) else match.start()
        if 0 < position < len(request):
            positions.add(position)
    return [
        {
            "id": f"b{index}",
            "offset": offset,
            "left": request[:offset],
            "right": request[offset:],
        }
        for index, offset in enumerate(sorted(positions)[:16])
    ]


def decomposition_schema(context):
    candidates = source_boundaries(context["request"])
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "cuts": {
                "type": "array",
                "minItems": 0,
                "maxItems": min(2, len(candidates)),
                "items": {
                    "type": "string",
                    "enum": [c["id"] for c in candidates] or ["no_boundary"],
                },
            }
        },
        "required": ["cuts"],
    }


def source_spans(request, decomposition):
    """Partition exact source at model-selected syntactic candidate boundaries.

    Every character is assigned exactly once. Candidate boundaries do not prove
    atomicity or semantic completeness; those need independent model testing.
    """
    candidates = {c["id"]: c for c in source_boundaries(request)}
    cuts = decomposition.get("cuts")
    if (
        set(decomposition) != {"cuts"}
        or not isinstance(cuts, list)
        or len(cuts) > 2
        or any(not isinstance(key, str) or key not in candidates for key in cuts)
        or len(cuts) != len(set(cuts))
    ):
        raise ValueError("Invalid source split boundaries")
    offsets = [candidates[key]["offset"] for key in cuts]
    if offsets != sorted(offsets) or not request.strip():
        raise ValueError("Question boundaries must be ordered and nonempty")
    cursor, spans = 0, []
    for end in [*offsets, len(request)]:
        spans.append(
            {
                "index": len(spans),
                "start": cursor,
                "end": end,
                "text": request[cursor:end],
            }
        )
        cursor = end
    assert "".join(span["text"] for span in spans) == request
    return spans


def interpret_question(context, infer, cancel, *, trace=None):
    """Bounded model interpretation; source coverage is separate from relevance.

    infer(context, schema, cancel) shares the caller's fixed authority and captured
    evidence. All calls and selections are recorded, including rejected outputs.
    """
    import hashlib

    trace = trace if trace is not None else {}
    trace.update(
        {
            "calls": 0,
            "max_calls": MAX_QUESTION_CALLS,
            "max_generated_tokens": MAX_QUESTION_GENERATED_TOKENS,
            "snapshot_id": hashlib.sha256(
                json.dumps(context["evidence"], sort_keys=True).encode()
            ).hexdigest(),
            "coverage": [],
        }
    )

    def call(value, schema):
        if cancel.is_set():
            raise ValueError(
                "Question canceled or deadline exceeded; no gameplay authorized"
            )
        if trace["calls"] >= MAX_QUESTION_CALLS:
            raise ValueError("Question interpretation call budget exhausted")
        trace["calls"] += 1
        result = infer(value, schema, cancel)
        if cancel.is_set():
            raise ValueError(
                "Question canceled or deadline exceeded; no gameplay authorized"
            )
        return result

    split_context = {
        "request": context["request"],
        "question_stage": "decompose",
        "read_only_question": True,
        "reference_context": context.get("reference_context", []),
    }
    split_context["boundary_candidates"] = source_boundaries(context["request"])
    trace["decomposition"] = call(split_context, decomposition_schema(context))
    spans = source_spans(context["request"], trace["decomposition"])
    trace["source_spans"] = spans
    replies, seen, supported = [], set(), False
    for span in spans:
        focused = {
            **context,
            "request": span["text"],
            "question_stage": "select_span",
            "source_question": context["request"],
            "source_span": span,
            "snapshot_id": trace["snapshot_id"],
        }
        selection = call(focused, selection_schema(context))
        row = {
            "span": span,
            "selection": selection,
            "snapshot_id": trace["snapshot_id"],
        }
        trace["coverage"].append(row)
        ids = selected_ids(context, selection)
        row["claims"] = {key: context["evidence"][key] for key in ids}
        supported = supported or ids != ["unknown"]
        for key in ids:
            if key == "unknown":
                replies.append(
                    "For "
                    + json.dumps(span["text"])
                    + ": "
                    + context["evidence"][key]["text"]
                )
            elif key not in seen:
                replies.append(context["evidence"][key]["text"])
            seen.add(key)
    if len(trace["coverage"]) != len(spans):
        raise ValueError("Question coverage incomplete")
    return {
        "kind": "question" if supported else "unavailable",
        "reply": "\n\n".join(replies),
    }


def conversation_context(context):
    """Natural read-only beta conversation with explicit application/state facts.

    Facts inform the response, not a finite menu of permitted conversation topics.
    General Minecraft advice is allowed, but uncertain advice is not world evidence.
    """
    captured = question_context(context)
    return {**captured, 'question_stage': 'conversation',
            'recent_conversation': deepcopy(context.get('recent_conversation', [])[-6:])}
