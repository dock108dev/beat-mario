from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from smb3_agent.learning import (
    CandidateLifecycle,
    LearningError,
    LocalLearningStore,
    PromotionDecision,
)
from smb3_agent.route_patch import (
    PATCH_ARTIFACTS_ROOT,
    RoutePatchError,
    compare_route_patch,
    promote_route_patch,
    rollback_route_patch,
)


def promote_learning_candidate(
    store: LocalLearningStore,
    candidate_id: str,
    route_patch_id: str,
    *,
    replay_evidence_references: tuple[str, ...],
    affected_reliability_evidence: tuple[str, ...],
    previous_solution_id: str | None,
    promoted_solution_id: str,
    repo_root: Path | None = None,
    artifacts_root: Path = PATCH_ARTIFACTS_ROOT,
    actor: str,
) -> PromotionDecision:
    candidate = next(
        (item for item in store.snapshot().candidates if item.candidate_id == candidate_id),
        None,
    )
    if candidate is None:
        raise LearningError(f"unknown learning candidate: {candidate_id}")
    if candidate.lifecycle is not CandidateLifecycle.REPLAY_VERIFIED:
        raise LearningError("candidate must be replay-verified before route-patch promotion")
    if not replay_evidence_references or not affected_reliability_evidence:
        raise LearningError("promotion requires replay and affected reliability evidence")

    comparison = compare_route_patch(
        route_patch_id,
        repo_root=repo_root,
        artifacts_root=artifacts_root,
    )
    if not comparison.details.get("promotion_recommended"):
        raise LearningError("route-patch comparison does not recommend exact-diff promotion")
    exact_diff_reference = str(comparison.artifact_path)
    store.mark_promotion_ready(
        candidate_id,
        route_patch_id=route_patch_id,
        exact_diff_reference=exact_diff_reference,
        reliability_evidence=affected_reliability_evidence,
        actor=actor,
    )
    decision = PromotionDecision(
        candidate_id,
        candidate.content_hash,
        exact_diff_reference,
        route_patch_id,
        replay_evidence_references,
        affected_reliability_evidence,
        previous_solution_id,
        promoted_solution_id,
        datetime.now(timezone.utc).isoformat(),
    )
    promoted = False
    try:
        promote_route_patch(
            route_patch_id,
            confirm_patch_id=route_patch_id,
            repo_root=repo_root,
            artifacts_root=artifacts_root,
            actor=actor,
        )
        promoted = True
        store.promote(decision, actor=actor)
    except Exception:
        if promoted:
            rollback_route_patch(
                route_patch_id,
                confirm_patch_id=route_patch_id,
                reason="learning registry failed after route-patch promotion",
                repo_root=repo_root,
                artifacts_root=artifacts_root,
                actor="automatic-compensation",
            )
        raise
    return decision


def rollback_learning_candidate(
    store: LocalLearningStore,
    candidate_id: str,
    *,
    reason: str,
    repo_root: Path | None = None,
    artifacts_root: Path = PATCH_ARTIFACTS_ROOT,
    actor: str,
) -> None:
    promotion = next(
        (
            item
            for item in reversed(store.snapshot().promotions)
            if item.candidate_id == candidate_id
        ),
        None,
    )
    if promotion is None:
        raise LearningError("candidate has no promotion to roll back")
    try:
        rollback_route_patch(
            promotion.route_patch_id,
            confirm_patch_id=promotion.route_patch_id,
            reason=reason,
            repo_root=repo_root,
            artifacts_root=artifacts_root,
            actor=actor,
        )
    except RoutePatchError as exc:
        raise LearningError(f"route-patch rollback failed: {exc}") from exc
    store.rollback(candidate_id, reason=reason, actor=actor)
