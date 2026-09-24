"""Mario-owned planning vocabulary and truthful registry-backed route identity."""
from __future__ import annotations

import re

from smb3_agent.goals import load_goal_contract, resolve_goal_path
from smb3_agent.request_planning import (
    AdapterProposal, PlannedAction, PlanningContext, is_negated, speed_from_text,
)
from smb3_agent.takeover import supported_solutions

BASE_ROUTE_ID = "world_8_finish_game"
DEFAULT_PRIMITIVE_ID = "world_1_1_default_v1"
HOP_PRIMITIVE_ID = "world_1_1_opening_hop_v1"
OPENING_BOUNDARY = "world_1_1_opening"
SUPPORTED_STOP_POINTS = ("world_1_1_opening_end", "world_1_1_exit", "full_route")


def resolve_base_route() -> dict[str, object]:
    """Resolve the real goal and accepted solution; never mint accepted variants."""
    goal = load_goal_contract(resolve_goal_path(BASE_ROUTE_ID))
    solution = next((item for item in supported_solutions()
                     if item.policy_id == BASE_ROUTE_ID and item.executable), None)
    if goal.id != BASE_ROUTE_ID or not goal.executable or solution is None:
        raise ValueError("The existing Mario base route is not available in the route registry.")
    return {"goal_id": goal.id, "solution_id": solution.solution_id,
            "solution_version": solution.version, "segments": goal.segments,
            "display_name": goal.display_name}


def _positive(pattern: str, text: str) -> bool:
    return any(not is_negated(text, match.start()) for match in re.finditer(pattern, text))


class MarioPlanningAdapter:
    help_text = ("I can prepare the existing route, use the opening hop or default path in World 1-1, "
                 "and stop after the opening, after World 1-1, or at the ending. "
                 "Specify the path or stop point; arbitrary routes need a new controller.")

    def propose(self, text: str, context: PlanningContext) -> AdapterProposal:
        current = context.current_plan
        requested = current.requested_objective if current else text
        intent = current.normalized_intent if current else "base_route"
        ambiguities: list[str] = []
        unsupported: list[str] = []
        changes: list[str] = []
        scopes: list[str] = []
        path_choice = "default"
        if current:
            path_choice = next((str(action.parameters["path_choice"]) for action in current.actions
                                if "path_choice" in action.parameters), "default")
        stop = current.stop_point if current and current.stop_point in SUPPORTED_STOP_POINTS else "full_route"
        original_stop = stop
        speed = speed_from_text(text)
        recognized = False

        try:
            base = resolve_base_route()
        except ValueError as exc:
            return AdapterProposal(intent, requested, (), base_route_id=BASE_ROUTE_ID,
                                   unsupported_parts=(str(exc),), execution_eligibility="blocked")

        optimize = _positive(r"\b(?:faster|fastest|quickest|quicker|shortest|speedrun|speed run|optimi[sz]e|optimal)\b", text)
        full = _positive(r"(?:100\s*%|\b(?:one hundred percent|full completion|everything|all (?:the )?(?:coins|collectibles|secrets)|complete clear)\b)", text)
        explicit_base = _positive(r"\b(?:base|original|normal|standard|existing|default|regular)\s+(?:route|plan|clear)\b|^(?:base|normal|default)$", text)
        if full:
            recognized = True
            intent, requested = "full_completion", text
            changes.append("Requested full completion; loaded the existing base route.")
            if not current or current.normalized_intent != intent:
                scopes.append("objective")
            if re.search(r"\b(?:measure|score|prove|verify|count)\b", text):
                ambiguities.append("Define the level or route and a finite observable completion checklist before scoring 100%; collectible coverage is unknown.")
        elif optimize:
            recognized = True
            intent, requested = "optimize_time", text
            changes.append("Requested a quicker game-frame route; loaded the existing base route.")
            if not current or current.normalized_intent != intent:
                scopes.append("objective")
        elif explicit_base or (current and re.search(r"\b(?:not|don't|do not)\s+(?:the )?(?:fastest|quickest|faster)\b", text)):
            recognized = True
            intent, requested = "base_route", text
            changes.append("Use the existing base route.")
            if not current or current.normalized_intent != intent:
                scopes.append("objective")

        hop_pattern = (r"\b(?:opening[ _-]hop|early[ _-](?:hop|jump)|hop(?:ping)?(?: (?:at|through|across))? (?:the )?opening|"
                       r"jump(?:ing)? (?:along|through|across|at) (?:the )?(?:opening|start)|"
                       r"(?:alternate|alternative|other) (?:opening |early )?(?:path|traversal|route))\b")
        hop_matches = list(re.finditer(hop_pattern, text))
        default_matches = list(re.finditer(r"\b(?:default|original|normal|standard|base|regular) (?:opening |early )?(?:path|traversal)\b", text))
        hop = any(not is_negated(text, match.start()) for match in hop_matches)
        default = any(not is_negated(text, match.start()) for match in default_matches)
        if hop and default:
            # Corrections choose the final explicitly contrasted choice, never arbitrary clause order.
            if re.search(r"\b(?:instead|rather than|actually|not)\b", text):
                last_hop = max(match.start() for match in hop_matches if not is_negated(text, match.start()))
                last_default = max(match.start() for match in default_matches if not is_negated(text, match.start()))
                hop, default = last_hop > last_default, last_default > last_hop
            else:
                ambiguities.append("Choose one World 1-1 opening path: default or opening hop.")
        if hop_matches or default_matches:
            recognized = True
            scopes.append("path")
            if hop and not default:
                if re.search(r"\bother (?:path|route)\b", text) and not current:
                    ambiguities.append("Select a current path before referring to the other path.")
                if re.search(r"\bother (?:path|route)\b", text) and current and path_choice == "opening_hop":
                    path_choice = "default"
                else:
                    path_choice = "opening_hop"
            elif default or (hop_matches and not hop):
                path_choice = "default"
            elif default_matches and not default:
                ambiguities.append("The default path was excluded; choose the supported opening hop explicitly.")
            changes.append("Take the opening hop in World 1-1." if path_choice == "opening_hop" else "Take the default World 1-1 opening path.")

        opening_stop = _positive(r"\b(?:stop|finish|end|halt)(?:\s+\w+){0,3}\s+(?:opening|first (?:hop|jump)|opening_end)\b|\bworld_1_1_opening_end\b", text)
        level_stop = _positive(r"\b(?:stop|finish|end|halt|only)(?:\s+\w+){0,5}\s+(?:world\s*1[ -]1|level\s*(?:1|one)|first level|first course)\b|\bworld_1_1_exit\b", text)
        if re.search(r"\b(?:don't|do not|never) (?:go|continue|play) (?:beyond|past) (?:the )?(?:first level|first course|world\s*1[ -]1)\b", text):
            level_stop = True
        if re.search(r"\b(?:world\s*1[ -]1|first level|first course)(?:\s+\w+){0,4}\s+(?:then stop|and stop|only)\b", text):
            level_stop = True
        ending_stop = _positive(r"\b(?:full_route|(?:to|at|through|reach|finish) (?:the )?(?:ending|credits|end of (?:the )?game)|finish (?:the )?game)\b", text)
        stop_count = int(opening_stop) + int(level_stop) + int(ending_stop)
        if stop_count:
            recognized = True
            scopes.append("stop_point")
            if stop_count > 1:
                ambiguities.append("Choose one stop point: opening, World 1-1 exit, or the ending.")
            elif opening_stop:
                stop = "world_1_1_opening_end"
            elif level_stop:
                stop = "world_1_1_exit"
            else:
                stop = "full_route"
            changes.append({"world_1_1_opening_end": "Stop after the World 1-1 opening.",
                            "world_1_1_exit": "Stop after clearing World 1-1.",
                            "full_route": "Continue to the existing route's ending."}[stop])
        if current and SUPPORTED_STOP_POINTS.index(stop) > SUPPORTED_STOP_POINTS.index(original_stop):
            scopes.append("expanded_scope")

        if re.search(r"\b(?:there|that one|this one|selected|highlighted)\b", text):
            recognized = True
            selected = context.selected_targets
            if len(selected) != 1:
                ambiguities.append("Select one observable Mario path or stop point so I can resolve that reference.")
            else:
                target = selected[0]
                target_id = str(target.get("id", target.get("target_id", "")))
                if target.get("visible") is False or target.get("occluded") is True:
                    ambiguities.append("The selected Mario target is not currently observable.")
                elif target_id in SUPPORTED_STOP_POINTS:
                    stop = target_id
                    scopes.append("stop_point")
                    changes.append(f"Use the selected stop point: {stop}.")
                elif target_id in {DEFAULT_PRIMITIVE_ID, HOP_PRIMITIVE_ID}:
                    path_choice = "opening_hop" if target_id == HOP_PRIMITIVE_ID else "default"
                    scopes.append("path")
                    changes.append(f"Use the selected {path_choice.replace('_', ' ')} path.")
                else:
                    unsupported.append("The selected Mario target has no implemented path or stop-point primitive.")

        if re.search(r"\b(?:water|harvest|plant|farm|crops|seeds|debris)\b", text):
            recognized = True
            unsupported.append("Farm actions belong to Stardew; switch games and select its targets.")
        if _positive(r"\b(?:teleport|savestate|warp|buy|sell|purchase|inject|execute|shell|delete)\b", text):
            recognized = True
            unsupported.append("That action is outside the ordinary-input Mario planning capabilities.")
        if re.search(r"\b(?:upper|lower|underground|secret|left-hand|right-hand) (?:path|route)|\b(?:world|level)\s*(?:[2-9]|1[ -][2-9])\b", text) and not optimize and not full:
            recognized = True
            unsupported.append("Custom traversal is currently limited to the World 1-1 default/opening-hop paths and declared stop points.")
        if speed is not None:
            recognized = True
            scopes.append("speed")
            changes.append(f"Request {speed:g}x playback." if isinstance(speed, (float, int)) else "Request uncapped turbo playback; actual speed is measured by the runtime.")
        if not recognized and re.search(r"\b(?:route|plan|play|mario|start|run|ending|quickest|100%)\b", text):
            # Vague path editing is not silently converted into the base route.
            if re.search(r"\b(?:change|edit|different|adjust|somewhere|avoid|skip)\b", text):
                ambiguities.append("Specify the World 1-1 opening path or supported stop point you want to change.")
            recognized = True
        if recognized:
            for clause in re.split(r"[,;]|\b(?:and then|then|and|but)\b", text):
                clause = clause.strip()
                if not clause:
                    continue
                known = re.search(r"\b(?:route|path|plan|opening|hop|jump|world|level|ending|credits|speed|playback|turbo|base|default|stop|normal|quickest|fastest|faster|quick|clear|completion|coins|collectibles|secrets|everything|selected|there|that one|this one)\b|100\s*%|\d\s*x\b", clause)
                if not known and not re.fullmatch(r"(?:please|actually|okay|ok|no|yes|instead|thanks|thank you)[.!?]*", clause):
                    unsupported.append(f"Unimplemented part of the request: {clause}.")
        if re.search(r"\b(?:don't|do not|never)\s+(?:play|run|use|set|switch)(?:\s+\w+){0,2}\s+(?:turbo|\d+(?:\.\d+)?x)\b", text):
            speed = None
            ambiguities.append("That playback setting was excluded; choose normal speed or turbo explicitly.")
        if not recognized:
            return AdapterProposal(intent, requested, (), recognized=False)

        if path_choice == "opening_hop" and stop != "world_1_1_opening_end":
            if stop_count or any(target.get("id") in {"world_1_1_exit", "full_route"} for target in context.selected_targets):
                ambiguities.append("The opening hop supports only the opening segment; confirm stopping after the opening or choose the default path for the longer destination.")
            stop = "world_1_1_opening_end"
            scopes.append("stop_point")
            changes.append("The opening hop is bounded to the opening segment and stops there; continuation through the rest of the level is unvalidated.")

        fallback = ""
        if intent == "optimize_time":
            fallback = "No optimized variant is available. The loaded route is world_8_finish_game; playback speed does not establish a faster game-frame route."
        elif intent == "full_completion":
            fallback = "No full-completion variant is available. The loaded route is world_8_finish_game; finishing it does not establish 100% completion, and coverage remains unknown."
        if not changes:
            changes.append("Prepare the existing world_8_finish_game base route; selecting it does not reset gameplay.")
        primitive = HOP_PRIMITIVE_ID if path_choice == "opening_hop" else DEFAULT_PRIMITIVE_ID
        actions = (PlannedAction(
            action_id="mario-traversal", kind="mario_traverse", target_ids=("world_1_1",),
            parameters={"primitive_id": primitive, "path_choice": path_choice, "base_route_id": BASE_ROUTE_ID,
                        "base_solution_id": base["solution_id"], "stop_point": stop},
            preconditions=("fresh_same_process_observation", "compatible_supported_entry_boundary", "runtime_validated_primitive", "fresh_bounded_authorization"),
            expected_outcomes=(f"observe_{stop}", "record_actual_game_frame_timing", "neutralize_and_return_control"),
        ),)
        return AdapterProposal(
            normalized_intent=intent, requested_objective=requested, actions=actions,
            base_route_id=BASE_ROUTE_ID, ambiguities=tuple(ambiguities), unsupported_parts=tuple(unsupported),
            protected_choices=("no_implicit_restart", "no_savestate_or_state_mutation", "completed_steps_are_history", "player_reclaim_wins"),
            resource_limits={"timeout_seconds": 2400, "max_pending_revisions": 1},
            stop_point=stop, effective_boundary=OPENING_BOUNDARY,
            requested_speed=speed, fallback_explanation=fallback, change_summary=tuple(changes),
            changed_scopes=tuple(dict.fromkeys(scopes)),
        )
