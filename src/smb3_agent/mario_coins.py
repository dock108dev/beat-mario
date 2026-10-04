"""Experimental World 1-1 route discovery from game-owned level coin counters.

Segment yields are opportunities, never identities of individual coins. Hidden,
brick, airborne and bonus-room coverage remains unverified in this first slice.
"""
from __future__ import annotations

import re

COMPATIBILITY = "smb3/world-1-1/coin-discovery/v1"
ROUTES = ("coin_high", "coin_low", "coin_balanced")
STAIRS_TACTIC = "land_then_cross_v1"
PIPE_TACTIC = "land_on_pipe_then_cross_v1"
GUIDANCE_CONTRACT = "smb3/world-1-1/route-guidance/v1"
LANDMARKS = ("opening", "first_pipes", "middle_gap", "stairs", "last_pipes", "goal")
COVERAGE = "Observed World 1-1 level-counter increases along surface routes; individual coin locations, hidden/brick coins, airborne and bonus-room opportunities remain unknown. Total coin set unverified; no 100% claim."


def coin_request(text: str) -> bool:
    value = text.lower()
    return bool((re.search(r"\bcoins?\b", value) or re.search(r"\b(?:stairs|traversal)\b", value)) and re.search(
        r"\b(?:find|collect|gather|get|explore|route|reach|finish|end|all|100|improve|past|through|navigate)\b", value))


def reconcile(events: list[dict], *, finished: bool) -> dict:
    """Deduplicate frame observations, refuse resets/gaps, retain partial totals."""
    samples = {}
    conflict = False
    for row in events:
        if row.get("event") != "coin_observation":
            continue
        try:
            frame, counter, x = int(row["frame"]), int(row["counter"]), int(row["x"])
        except (KeyError, ValueError, TypeError):
            conflict = True
            continue
        if not 0 <= counter <= 255 or not 0 <= x < 8192:
            conflict = True
            continue
        if frame in samples and samples[frame] != (counter, x):
            conflict = True
        samples[frame] = (counter, x)
    total = 0
    yields = dict.fromkeys(LANDMARKS, 0)
    visited = set()
    previous = None
    max_x = 0
    for frame, (counter, x) in sorted(samples.items()):
        index = min(x // 500, len(LANDMARKS) - 1)
        landmark = LANDMARKS[index]
        visited.add(landmark)
        max_x = max(max_x, x)
        if previous is not None:
            old_frame, old_counter = previous
            delta = counter - old_counter
            # Per-frame native observations are required. Resets, wraps and
            # discontinuities cannot be explained by a guessed coin pickup.
            if delta < 0 or delta > 1 or frame - old_frame != 1:
                conflict = True
            else:
                total += delta
                yields[landmark] += delta
        previous = (frame, counter)
    completed = [name for i, name in enumerate(LANDMARKS)
                 if max_x >= (i + 1) * 500 or (finished and name in visited)]
    return {"collected": total if samples and not conflict else None,
            "observed_increases": total, "accounting_uncertain": conflict or not samples,
            "segment_yields": yields, "visited_landmarks": sorted(visited),
            "completed_landmarks": completed,
            "unvisited_landmarks": [name for name in LANDMARKS if name not in completed], "furthest_x": max_x if samples else None,
            "level_finish_observed": finished, "coverage": COVERAGE,
            "full_declared_set_verified": False, "complete": False}


def compatible(history: list[dict], cartridge: str | None) -> list[dict]:
    if not cartridge:
        return []
    return [row for row in history if row.get("cartridge_sha256") == cartridge
            and row.get("initial_plan", {}).get("coin_compatibility") == COMPATIBILITY
            and row.get("coin_result", {}).get("controller_application_observed")]


def knowledge(history: list[dict], cartridge: str | None) -> dict:
    rows = compatible(history, cartridge)
    best = dict.fromkeys(LANDMARKS, 0)
    for row in rows:
        result = row["coin_result"]
        if result.get("collected") is not None:
            for name in LANDMARKS:
                best[name] = max(best[name], result["segment_yields"].get(name, 0))
    return {"attempts": len(rows), "best_observed_segment_yields": best,
            "known_opportunity_lower_bound": max((row["coin_result"]["collected"] for row in rows
                if row["coin_result"].get("collected") is not None), default=0),
            "coverage": COVERAGE, "complete": False,
            "routes_tried": [row["initial_plan"]["path_choice"] for row in rows],
            "archived_attempts": sum(bool(row.get("coin_result")) for row in history),
            "compatibility_pending": not bool(cartridge)}


def choose_route(history: list[dict], cartridge: str | None) -> tuple[str, str]:
    rows = compatible(history, cartridge)
    finished = [row for row in rows if row["coin_result"].get("level_finish_observed")
                and row["coin_result"].get("collected") is not None]
    if finished and (any(row["initial_plan"].get("route_guidance") for row in finished)
                     or set(ROUTES).issubset({row["initial_plan"]["path_choice"] for row in rows})):
        best = max(finished, key=lambda row: row["coin_result"]["collected"])
        return best["initial_plan"]["path_choice"], "Reuse the route with an observed level finish and the best measured coin yield; full coin coverage remains unknown."
    stairs_failures = [row for row in rows if row.get("status") == "death"
                       and row["initial_plan"]["path_choice"] == "coin_balanced"
                       and 1500 <= (row["coin_result"].get("furthest_x") or 0) <= 1750]
    if stairs_failures:
        return "coin_balanced", "Remembered balanced-route death at the stairs: preserve its approach and two-coin discovery, then land on the left stair top, release jump and launch a running jump across the gap. Finish and coverage still require observation."
    tried = {row["initial_plan"]["path_choice"] for row in rows}
    for route in ROUTES:
        if route not in tried:
            return route, ("Explore an untried surface alternative: " +
                           ("earlier, longer scheduled jumps" if route == "coin_high" else
                            "later, shorter scheduled jumps" if route == "coin_low" else
                            "preserve the opening through x=700, then try earlier, longer jumps in later landmark bands") +
                           ". Compare observed coin yields and failures at six landmarks.")
    # A failed/uncertain latest attempt prompts a real alternative, never a
    # repeated summary. Otherwise exploit the best independently measured yield.
    latest = rows[0]
    if latest.get("status") != "completed_stop" or latest["coin_result"].get("collected") is None:
        route = max(rows, key=lambda row: row["coin_result"].get("furthest_x") or 0)["initial_plan"]["path_choice"]
        return route, "The latest attempt failed or has uncertain accounting; reuse the pattern with the furthest observed progress after exploring the alternatives."
    measured = [row for row in rows if row["coin_result"].get("collected") is not None]
    best = max(measured, key=lambda row: (row["coin_result"]["level_finish_observed"], row["coin_result"]["collected"]))
    return best["initial_plan"]["path_choice"], "Reuse the best observed finished-route coin yield; coverage is still unknown."


def route_guidance(history: list[dict], cartridge: str | None) -> dict | None:
    failures = [row for row in compatible(history, cartridge) if row.get("status") == "death"
                and 1500 <= (row["coin_result"].get("furthest_x") or 0) <= 1750]
    if not failures:
        return None
    guidance = {"contract": GUIDANCE_CONTRACT, "stairs_tactic": STAIRS_TACTIC,
            "instruction": "Land on the left stair top, release jump, then run and jump across the gap.",
            "basis": "observed_stairs_death", "source_attempt_ids": [row.get("attempt_id") for row in failures],
            "cartridge_sha256": cartridge, "application": "next_compatible_attempt"}
    pipe_failures = [row for row in compatible(history, cartridge) if row.get("status") == "death"
                     and row["coin_result"].get("stairs_landing_observed")
                     and 1800 <= (row["coin_result"].get("furthest_x") or 0) <= 1950]
    if pipe_failures:
        guidance.update(pipe_tactic=PIPE_TACTIC,
                        pipe_instruction="Land on the first pipe, take a short run-up on its top, then jump across the next pipe, preserving height instead of retreating to the ground.",
                        pipe_source_attempt_ids=[row.get("attempt_id") for row in pipe_failures])
    return guidance


def report(result: dict) -> str:
    collected = result.get("collected")
    missed = result.get("known_missed_lower_bound")
    return (f"Collected this attempt: {collected if collected is not None else 'unknown'}; "
            f"known missed opportunity lower bound: {missed if missed is not None else 'unknown'}. "
            f"Furthest observed position: {result.get('furthest_x') if result.get('furthest_x') is not None else 'unknown'}. "
            f"Level finish: {'observed' if result.get('level_finish_observed') else 'unverified'}. "
            + ("Next-attempt stairs instruction: " + result["route_guidance"]["instruction"] +
               f" Controller application: {'observed' if result.get('guidance_application_observed') else 'unverified'}; " +
               f"landing beyond stairs: {'observed' if result.get('stairs_landing_observed') else 'unverified'}. "
               if result.get("route_guidance") else "") + COVERAGE)
