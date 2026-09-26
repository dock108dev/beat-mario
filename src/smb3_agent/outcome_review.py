"""Read-only outcome presentation shared by both game workspaces."""
from typing import Any


def outcome_review(record: dict[str, Any]) -> dict[str, Any]:
    status = str(record.get("status") or "unknown")
    reason = str(record.get("first_unmet_requirement") or record.get("stop_reason") or record.get("reason") or "")
    ledger = record.get("task_ledger") or {}
    steps = ledger.get("steps") or []
    confirmed = [f"{s['kind']} {s['target_id']}" for s in steps if s.get("status") == "confirmed"]
    confirmed += [f"{s['kind']} {s['target_id']} (already satisfied before this run)"
                  for s in steps if s.get("status") == "already_satisfied"]
    remaining = [f"{s['kind']} {s['target_id']}: {s.get('status', 'unknown')}"
                 for s in steps if s.get("status") not in {"confirmed", "already_satisfied"}]
    guarded = any(word in (status + " " + reason).lower() for word in ("occlu", "guard", "uncertain"))
    completed = status in {"completed", "completed_bounded_plan", "task_completed", "completed_stop"} and not guarded
    if not steps and ledger:
        confirmed = [f"{ledger.get('watered_count', 'Unknown')} crops confirmed watered"]
        remaining = [f"{ledger.get('remaining_count', 'Unknown')} crops remaining to reconcile"]
    if ledger and not (ledger.get("final_position") or {}).get("at_farmhouse_entrance"):
        remaining.append("Farmhouse return not confirmed")
    plan = record.get("reviewed_plan") or record.get("actual_plan") or record.get("initial_plan") or {}
    return {
        "label": "Guarded stop — not complete" if guarded else status.replace("_", " ").capitalize(),
        "reason": reason,
        "request": plan.get("original_request") or record.get("request") or "Request not retained in this older record",
        "confirmed": confirmed,
        "remaining": remaining or (["Reviewed scope complete; no automatic continuation"] if completed else ["Reconcile the last observed state before choosing remaining work"]),
        "recovery": "History is read-only; no control permission is restored. " + (
            "For Stardew, obtain a clear supported view or open a fresh disposable copy, Observe, request only remaining work, review the entire plan, then Start. Never automatically resume a guarded stop."
            if record.get("game_id") == "stardew" else
            "For Mario, open a compatible visible session, select or reopen a route, review it, then Start. Completed game actions cannot be undone."),
    }
