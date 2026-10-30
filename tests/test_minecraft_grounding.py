import threading

import pytest

from smb3_agent.minecraft_grounding import (
    QuestionDeadline,
    compose_answer,
    question_context,
)


def test_current_work_does_not_replace_historical_receipts():
    context = question_context(
        {
            "request": "Was anything built before this run?",
            "project": {
                "state": "running",
                "current_work": {"verified_units_in_current_run": 0},
                "receipt_history": {"verified_receipts_across_all_revisions": 12000},
            },
            "history": [{"role": "assistant", "text": "Nothing was ever built."}],
        }
    )
    assert "12000" in context["evidence"]["saved_history"]["text"]
    assert "0 verified units" in context["evidence"]["current_work"]["text"]
    assert "history" not in context
    selected = compose_answer(context, {"fact_ids": ["saved_history", "current_work"]})
    assert "12000" in selected["reply"] and "0 verified units" in selected["reply"]


@pytest.mark.parametrize(
    "ids", [[], ["invented"], ["stop", "stop"], "stop", [None], ["stop"] * 5]
)
def test_bad_fact_selection_is_rejected(ids):
    with pytest.raises(ValueError):
        compose_answer(question_context({"request": "Hello"}), {"fact_ids": ids})


def test_shared_question_deadline_does_not_cancel_gameplay():
    now = [10.0]
    parent = threading.Event()
    deadline = QuestionDeadline(parent, 500, clock=lambda: now[0])
    assert deadline.until == 250
    now[0] = 249
    assert not deadline.is_set()
    now[0] = 250
    assert deadline.is_set()
    assert not parent.is_set()
    fresh = QuestionDeadline(parent, 30, clock=lambda: now[0])
    parent.set()
    assert fresh.is_set()


def test_claims_cannot_be_rewritten_or_invert_unknown_into_absence():
    context = question_context({"request": "Any testing evidence?"})
    selection = {"fact_ids": ["native_test_evidence"]}
    answer = compose_answer(context, selection)
    assert "unknown" in answer["reply"]
    assert answer["reply"] == context["evidence"]["native_test_evidence"]["text"]
    with pytest.raises(ValueError):
        compose_answer(context, {**selection, "reply": "All tests failed."})
    with pytest.raises(ValueError):
        compose_answer(context, {"fact_ids": ["native_test_evidence", "unknown"]})
    with pytest.raises(ValueError):
        compose_answer(context, {**selection, "health": "false"})


def test_complete_procedure_survives_selection_and_state_contrasts():
    context = question_context(
        {
            "request": "Change dimensions?",
            "observations": {"health": 7, "held_item": None},
            "project": {
                "review_dependencies": {"reported_dependencies": ["clear entrance"]}
            },
        }
    )
    answer = compose_answer(context, {"fact_ids": ["change_dimensions"]})
    for step in range(1, 7):
        assert f"({step})" in answer["reply"]
    assert "if footprint or base elevation changes" in answer["reply"]
    assert "clear entrance" in context["evidence"]["review_dependencies"]["text"]
    assert "empty hand" in context["evidence"]["held_item"]["text"]
    assert context["evidence"]["food"]["modality"] == "unknown"
    assert context["evidence"]["health"]["modality"] == "observed_snapshot"


def test_source_coverage_rejects_rewrites_omissions_and_negation_loss():
    from smb3_agent.minecraft_grounding import source_spans

    text = "Does Stop NOT pause the world, and what is my health?"
    spans = source_spans(text, {"cuts": ["b0"]})
    assert "".join(s["text"] for s in spans) == text
    assert [text[s["start"] : s["end"]] for s in spans] == [s["text"] for s in spans]
    for parts in [
        ["Does Stop pause the world,", "and what is my health?"],
        ["Does Stop NOT pause the world,"],
        ["what is my health?"],
        ["Does Stop NOT pause the world,", "what is my health?"],
    ]:
        with pytest.raises(ValueError):
            source_spans(text, {"segments": parts})


def test_decomposition_preserves_supported_clause_alongside_unknown():
    from smb3_agent.minecraft_grounding import interpret_question

    context = question_context(
        {
            "request": "What is my health, and what is the weather in Rome?",
            "observations": {"health": 7},
        }
    )
    results = iter(
        [{"cuts": ["b0"]}, {"fact_ids": ["health"]}, {"fact_ids": ["unknown"]}]
    )
    calls = []

    def infer(ctx, schema, cancel):
        calls.append(ctx)
        return next(results)

    trace = {}
    answer = interpret_question(context, infer, threading.Event(), trace=trace)
    assert answer["kind"] == "question"
    assert "7" in answer["reply"] and "weather in Rome" in answer["reply"]
    assert "does not establish" in answer["reply"]
    assert trace["calls"] == 3
    assert len(trace["coverage"]) == 2
    assert all(row["snapshot_id"] == trace["snapshot_id"] for row in trace["coverage"])
    assert calls[1]["source_span"]["start"] == 0
    assert calls[2]["evidence"]["health"] == context["evidence"]["health"]


def test_invalid_decomposition_never_proceeds_to_fact_selection():
    from smb3_agent.minecraft_grounding import interpret_question

    calls = []

    def infer(ctx, schema, cancel):
        calls.append(ctx)
        return {"segments": ["What is my health?"]}

    with pytest.raises(ValueError):
        interpret_question(
            question_context({"request": "What is my health? And food?"}),
            infer,
            threading.Event(),
        )
    assert len(calls) == 1


def test_followup_reference_contains_only_prior_user_text():
    ctx = question_context(
        {
            "request": "And its contents?",
            "recent_conversation": [
                {"role": "user", "text": "Can you restore the chest block?"},
                {"role": "assistant", "text": "All diamonds are safe."},
                {"role": "user", "text": "And its contents?"},
            ],
        }
    )
    assert ctx["reference_context"] == [
        {"source": "prior_user_message", "text": "Can you restore the chest block?"}
    ]


@pytest.mark.parametrize("cuts", [[0], [-1], [99], [True], [2, 2], [3, 1], [1, 2, 3]])
def test_source_split_boundaries_must_be_unique_ordered_and_bounded(cuts):
    from smb3_agent.minecraft_grounding import source_spans

    with pytest.raises(ValueError):
        source_spans("One question and another question?", {"cuts": cuts})


def test_four_calls_share_one_deadline_and_never_refresh_evidence():
    from smb3_agent.minecraft_grounding import interpret_question

    now = [0.0]
    parent = threading.Event()
    deadline = QuestionDeadline(parent, 240, clock=lambda: now[0])
    results = iter(
        [
            {"cuts": ["b0", "b1"]},
            {"fact_ids": ["health"]},
            {"fact_ids": ["food"]},
            {"fact_ids": ["held_item"]},
        ]
    )

    def infer(ctx, schema, cancel):
        assert cancel is deadline
        now[0] += 61
        return next(results)

    trace = {}
    with pytest.raises(ValueError, match="deadline"):
        interpret_question(
            question_context(
                {
                    "request": "Health please? Food please? Hand please?",
                    "observations": {"health": 9},
                }
            ),
            infer,
            deadline,
            trace=trace,
        )
    assert trace["calls"] == 4 and not parent.is_set()
