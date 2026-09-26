"""Stardew-owned farm planning. Live eligibility requires the complete automatic observation and runtime validation.

Targets are supplied observations with stable id, kind (crop/plot/debris), and
optional label/patch/ready/planted/visible/confidence fields. References only
resolve within the active observation. This module never accesses a save.
"""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from smb3_agent.request_planning import AdapterProposal, PlannedAction, PlanningContext, is_negated

FARM_TASK_ID = "stardew_farm_routine_v1"
ACTION_WORDS = {
    "water": r"water(?:ing)?|irrigate|sprinkle",
    "harvest": r"harvest(?:ing)?|pick(?:ing)?(?: up)?|gather|collect",
    "plant": r"plant(?:ing)?|sow(?:ing)?",
    "clear": r"clear(?:ing)?|remove|chop|break",
}
ACTION_RE = re.compile(r"\b(?P<water>" + ACTION_WORDS["water"] + r")\b|\b(?P<harvest>" + ACTION_WORDS["harvest"] + r")\b|\b(?P<plant>" + ACTION_WORDS["plant"] + r")\b|\b(?P<clear>" + ACTION_WORDS["clear"] + r")\b")
TARGET_KINDS = {"water": {"crop", "plot"}, "harvest": {"crop"}, "plant": {"plot", "crop"}, "clear": {"debris"}}
PRECONDITIONS = {
    "water": ("visible_planted_target_set", "water_state_known", "watering_can_and_water_accounted", "energy_above_reviewed_limit"),
    "harvest": ("visible_ready_crops", "inventory_capacity", "crop_identity_and_regrowth_known", "energy_above_reviewed_limit"),
    "plant": ("owned_seed_type_and_count", "visible_empty_valid_plots", "season_compatible", "energy_above_reviewed_limit"),
    "clear": ("visible_selected_debris", "suitable_owned_tool", "crops_buildings_and_unselected_objects_protected", "energy_above_reviewed_limit"),
}
OUTCOMES = {
    "water": ("target_water_state_observed", "water_and_energy_reconciled"),
    "harvest": ("inventory_and_crop_post_state_reconciled", "regrowing_crops_preserved"),
    "plant": ("owned_seeds_consumed_reconciled", "newly_planted_tiles_observed"),
    "clear": ("selected_debris_removal_observed", "items_and_energy_reconciled", "unselected_objects_unchanged"),
}


def _id(target: dict[str, Any]) -> str:
    return str(target.get("id", target.get("target_id", "")))


def _targets(context: PlanningContext) -> list[dict[str, Any]]:
    """Deduplicate observations without inventing a target or broadening selection."""
    items = list(context.observation.get("targets", ())) + list(context.selected_targets)
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict) and _id(item):
            result[_id(item)] = item
    return list(result.values())


def _seed(clause: str) -> str | None:
    # Supported named seed identity is data; ownership/season are adapter preconditions.
    match = re.search(r"\b(?:plant|sow|use)\s+(?:only\s+)?(?:\d+\s+)?(?:the\s+)?([a-z][a-z-]*(?: [a-z][a-z-]*)?)\s+seeds?\b", clause)
    if match:
        value = match.group(1)
        return value if value not in {"these", "those", "selected", "owned", "my", "some", "the"} else None
    match = re.search(r"\b(?:plant|sow)\s+(?:\d+\s+)?(parsnips?|potatoes|potato|cauliflower|kale|beans?|corn|wheat|melons?|pumpkins?|cranberries|blueberries|strawberries)\b", clause)
    if match:
        return {"parsnips": "parsnip", "potatoes": "potato", "beans": "bean", "melons": "melon", "pumpkins": "pumpkin"}.get(match.group(1), match.group(1))
    return None


def _resolve_targets(kind: str, clause: str, context: PlanningContext,
                     prior: tuple[str, ...], ambiguities: list[str]) -> tuple[str, ...]:
    all_targets = _targets(context)
    compatible = [target for target in all_targets if target.get("kind") in TARGET_KINDS[kind]]
    if kind == "water":
        compatible = [target for target in compatible if target.get("kind") == "crop" or target.get("planted") is True
                      or (_id(target) in prior and re.search(r"\b(?:them|newly planted)\b", clause))]
    if kind == "plant" and re.search(r"\bplots?\b", clause):
        compatible = [target for target in compatible if target.get("kind") == "plot"]
    selected_ids = {_id(target) for target in context.selected_targets}
    candidates: list[dict[str, Any]] = []
    explicit = [target for target in compatible
                if re.search(r"(?<![\w-])" + re.escape(_id(target)) + r"(?![\w-])", clause)
                or (target.get("label") and str(target["label"]).lower() in clause)]
    patch_match = re.search(r"\b(?:north|south|east|west|left|right|upper|lower)\b", clause)
    if explicit:
        candidates = explicit
    elif "other patch" in clause or "other plot" in clause:
        groups: dict[str, list[dict[str, Any]]] = {}
        prior_groups = {str(target.get("patch", _id(target))) for target in compatible if _id(target) in prior}
        for target in compatible:
            group = str(target.get("patch", _id(target)))
            if group not in prior_groups:
                groups.setdefault(group, []).append(target)
        if len(groups) == 1 and prior_groups:
            candidates = next(iter(groups.values()))
        else:
            ambiguities.append("Select the other patch explicitly; more than one or no alternate patch is observable.")
            return ()
    elif patch_match:
        candidates = [target for target in compatible
                      if patch_match.group() in str(target.get("patch", "")).lower()
                      or patch_match.group() in str(target.get("label", "")).lower()]
    elif re.search(r"\b(?:selected|highlighted|these|those|this|that)\b", clause):
        candidates = [target for target in compatible if _id(target) in selected_ids]
    elif re.search(r"\b(?:them|same|again)\b", clause) and prior:
        candidates = [target for target in compatible if _id(target) in prior]
    elif re.search(r"\ball (?:the )?(?:visible|observed|initially planted|planted|crops)\b", clause):
        candidates = compatible
    elif selected_ids:
        candidates = [target for target in compatible if _id(target) in selected_ids]
    else:
        ambiguities.append(f"Select the observable targets to {kind}; the task does not authorize every object on the farm.")
        return ()
    if kind == "harvest" and re.search(r"\b(?:ready|ripe|mature)\b", clause):
        candidates = [target for target in candidates if target.get("ready") is True]
    if not candidates:
        ambiguities.append(f"No matching observable {kind} targets are selected.")
        return ()
    for target in candidates:
        if target.get("visible") is False or target.get("occluded") is True or float(target.get("confidence", 1)) < 0.9:
            ambiguities.append(f"Target {_id(target)} is occluded or insufficiently certain; observe it again.")
        if kind == "clear" and target.get("protected") is True:
            ambiguities.append(f"Target {_id(target)} is protected and cannot be cleared.")
        for field, expected in (("game_id", "stardew"), ("session_id", context.session_id), ("observation_id", context.observation_id)):
            if target.get(field) is not None and target[field] != expected:
                ambiguities.append(f"Target {_id(target)} belongs to another {field.replace('_', ' ')}; observe it again.")
    return tuple(_id(target) for target in candidates)


class StardewPlanningAdapter:
    help_text = ("I can plan watering, harvesting ready crops, planting owned seeds, and clearing selected debris. "
                 "Select observed targets and name the seed type for planting. Watering requires verified disposable setup and automatic complete-set perception. Harvest, planting and clearing await B4.")

    def propose(self, text: str, context: PlanningContext) -> AdapterProposal:
        current = context.current_plan
        actions = list(current.actions) if current else []
        ambiguities: list[str] = []
        unsupported: list[str] = []
        changes: list[str] = []
        protected = list(current.protected_choices) if current else [
            "preserve_primary_save", "protect_crops_buildings_and_unselected_objects", "no_purchases_sales_gifts_story_or_sleep", "player_reclaim_wins",
        ]
        limits = dict(current.resource_limits) if current else {"minimum_energy": None, "maximum_seeds": None, "stop_time": None, "purchases": 0}
        matches = list(ACTION_RE.finditer(text))
        recognized = bool(matches)
        correction = bool(re.search(r"\b(?:actually|instead|rather|no,|change|replace|other patch|other plot|only)\b", text))
        if re.search(r"\b(?:buy|purchase|sell|gift|sleep|primary save|story|attack|teleport)\b", text):
            dangerous = re.search(r"\b(?:buy|purchase|sell|gift|sleep|primary save|story|attack|teleport)\b", text)
            if dangerous and not is_negated(text, dangerous.start()):
                unsupported.append("Purchases, sales, gifts, story choices, sleeping, and primary-save changes are outside this farm routine.")
            recognized = True
        if re.search(r"\b(?:mario|world\s*1[ -]1|opening hop|bowser)\b", text):
            unsupported.append("Mario route targets cannot be used in a Stardew plan.")
            recognized = True

        # A noun-only correction resolves the previous action rather than inventing a new task.
        seed_correction = _seed(text) if re.search(r"\buse\b", text) else None
        if not matches and current and not re.search(r"\b(?:leave|spare|protect|avoid)\b", text) and (re.search(r"\b(?:other patch|other plot|these|those|selected)\b", text) or seed_correction):
            recognized = True
            if seed_correction:
                found = False
                for index, action in enumerate(actions):
                    if action.kind == "plant":
                        actions[index] = replace(action, parameters={**action.parameters, "seed_type": seed_correction})
                        found = True
                if not found:
                    ambiguities.append("There is no planting step to correct; select plots and request planting first.")
                else:
                    changes.append(f"Use owned {seed_correction} seeds for the planting step.")
            elif len(actions) == 1:
                action = actions[0]
                target_ids = _resolve_targets(action.kind, text, context, action.target_ids, ambiguities)
                actions[0] = replace(action, target_ids=target_ids)
                changes.append(f"Change {action.kind} targets to {', '.join(target_ids) or 'unresolved selection'}.")
            else:
                ambiguities.append("Specify which step to change: water, harvest, plant, or clear.")

        leave = re.search(r"\b(?:leave|spare|protect|avoid)\b(?!\s+(?:at least\s+)?\d+\s+energy)(.+?)(?:\s+alone|\s+untouched|[.;]|$)", text)
        if leave:
            recognized = True
            exclusions = {_id(target) for target in context.selected_targets}
            explicit = {_id(target) for target in _targets(context) if _id(target) in leave.group(1)}
            if explicit:
                exclusions = explicit
            if not exclusions:
                ambiguities.append("Select the objects to leave untouched.")
            else:
                protected.extend(f"leave_untouched:{item}" for item in sorted(exclusions))
                actions = [replace(action, target_ids=tuple(item for item in action.target_ids if item not in exclusions)) for action in actions]
                actions = [action for action in actions if action.target_ids]
                changes.append("Leave the selected objects untouched.")

        # Explicit ordered routines replace the previous proposed routine. A single
        # correction updates its action family; 'also/then/add' appends a new step.
        positive = [match for match in matches if not is_negated(text, match.start())]
        append = bool(re.search(r"^(?:and |also |then |add )", text))
        if len(positive) > 1 and not append:
            actions = []
        elif len(positive) == 1 and not current:
            actions = []
        prior_ids = current.actions[-1].target_ids if current and current.actions else ()
        new_plant_ids: tuple[str, ...] = ()
        for index, match in enumerate(matches):
            kind = str(match.lastgroup)
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            clause = text[match.start():end].strip(" ,;")
            if is_negated(text, match.start()):
                if re.search(r"\b(?:those|these|selected|highlighted)\b", clause) and context.selected_targets:
                    excluded = {_id(target) for target in context.selected_targets}
                    actions = [replace(action, target_ids=tuple(item for item in action.target_ids if item not in excluded))
                               if action.kind == kind else action for action in actions]
                    actions = [action for action in actions if action.target_ids]
                    protected.extend(f"do_not:{kind}:{item}" for item in sorted(excluded))
                else:
                    actions = [action for action in actions if action.kind != kind]
                    protected.append(f"do_not:{kind}")
                changes.append(f"Do not {kind}; remove that future step.")
                continue
            # A later explicit correction replaces earlier exclusion of this action.
            protected = [value for value in protected if value != f"do_not:{kind}"]
            previous_same = next((action for action in actions if action.kind == kind), None)
            referent = previous_same.target_ids if previous_same else prior_ids
            targets = _resolve_targets(kind, clause, context, referent, ambiguities)
            excluded = {value.split(":", 1)[1] for value in protected if value.startswith("leave_untouched:")}
            targets = tuple(item for item in targets if item not in excluded)
            params: dict[str, Any] = {"capability_status": "fixture_only_unavailable_live"}
            if kind == "plant":
                seed = _seed(clause)
                if seed is None and previous_same and (correction or append):
                    seed = previous_same.parameters.get("seed_type")
                if seed is None:
                    ambiguities.append("Name the owned seed type for planting; no purchase is implied.")
                count_match = re.search(r"\b(?:plant|sow)\s+(\d+)\b", clause)
                count = int(count_match.group(1)) if count_match else (len(targets) or None)
                if count is not None and count < 1:
                    ambiguities.append("Choose a positive seed count.")
                if count is not None and targets and count > len(targets):
                    ambiguities.append("The requested seed count exceeds the selected plot count; select the additional plots explicitly.")
                params.update({"seed_type": seed, "seed_count": count, "owned_seeds_only": True})
                new_plant_ids = targets
            elif kind == "water":
                params["preserve_initial_planted_set"] = True
                if new_plant_ids:
                    params["recompute_after_planting"] = True
                    params["newly_planted_target_ids"] = list(new_plant_ids)
                    # 'water them' after planting refers to those planned plot IDs.
                    if re.search(r"\b(?:them|those|newly planted)\b", clause):
                        targets = new_plant_ids
                    elif re.search(r"\ball\b", clause):
                        targets = tuple(dict.fromkeys((*targets, *new_plant_ids)))
            elif kind == "clear":
                params["selected_debris_only"] = True
            if previous_same and len(positive) == 1 and not append:
                position = actions.index(previous_same)
                action_id = previous_same.action_id
            else:
                position = len(actions)
                action_id = f"farm-{position + 1}-{kind}"
            action = PlannedAction(action_id, kind, targets, params,
                                   PRECONDITIONS[kind] + ("fresh_disposable_copy_identity", "live_perception_and_input_not_yet_available"), OUTCOMES[kind])
            if position < len(actions):
                actions[position] = action
            else:
                actions.append(action)
            prior_ids = targets
            changes.append(f"{kind.capitalize()} {', '.join(targets) or 'selected targets (unresolved)' }.")

        # Preserve explicitly requested order, but require clarification for a known
        # contradictory dependency rather than silently doing a different routine.
        for index, action in enumerate(actions):
            later = actions[index + 1:]
            if action.kind == "plant" and any(other.kind in {"harvest", "clear"} and set(other.target_ids) & set(action.target_ids) for other in later):
                ambiguities.append("Harvest or clear the overlapping targets before planting; confirm that order.")
            if action.kind == "plant" and index and any(other.kind == "harvest" and set(other.target_ids) & set(action.target_ids) for other in actions[:index]):
                actions[index] = replace(action, preconditions=action.preconditions + ("harvested_plot_observed_empty_not_regrowing",))
        energy = re.search(r"\b(?:leave|keep|at least|above|below)\s+(?:at least\s+)?(\d+)\s+energy\b", text)
        if energy:
            limits["minimum_energy"] = int(energy.group(1))
            recognized = True
        seeds = re.search(r"\b(?:at most|maximum|no more than)\s+(\d+)\s+seeds?\b", text)
        if seeds:
            limits["maximum_seeds"] = int(seeds.group(1))
            recognized = True
        stop_time = re.search(r"\b(?:stop|finish)\s+(?:by|at|before)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b", text)
        if stop_time:
            limits["stop_time"] = stop_time.group(1)
            recognized = True
        stop = current.stop_point if current else context.observation.get("return_point", "selected_return_point")
        return_match = re.search(r"\b(?:return|go back)\s+to\s+(?:the\s+)?([a-z][a-z -]*?)(?:[.,;]|$)", text)
        if return_match:
            stop = return_match.group(1).strip().replace(" ", "_")
            recognized = True
            # Return labels remain proposed; a live adapter must resolve a visible anchor.
        if not recognized:
            return AdapterProposal("farm_routine", text, (), recognized=False)
        for clause in re.split(r"[,;]|\b(?:and then|then|and|but)\b", text):
            clause = clause.strip()
            if not clause or re.fullmatch(r"(?:please|actually|okay|ok|no|yes|instead|thanks|thank you)[.!?]*", clause):
                continue
            known = ACTION_RE.search(clause) or re.search(r"\b(?:leave|spare|protect|avoid|energy|seeds|stop|return|go back|other patch|other plot|these|those|selected|buy|purchase|sell|gift|sleep|primary save|story|mario|opening hop)\b", clause)
            if not known:
                unsupported.append(f"Unimplemented part of the request: {clause}.")
        if not actions and not (leave or any(is_negated(text, match.start()) for match in matches)):
            ambiguities.append("Specify at least one bounded farm action and its selected targets.")
        fixture = context.observation.get("source") in {"fixture", "synthetic", "manual_fixture"} or context.observation.get("fixture") is True
        live = (context.observation_fresh is True
                and context.observation.get("source") == "automatic_visible"
                and context.observation.get("validated") is True
                and context.observation.get("complete_initial_set") is True
                and context.observation.get("isolation_verified") is True)
        watering_only = bool(actions) and all(action.kind == "water" for action in actions)
        from smb3_agent.stardew_farm_tasks import FARM_CONTRACT
        farm_live = (live and context.observation.get("farm_contract") == FARM_CONTRACT
                     and bool(actions) and all(a.kind in context.observation.get("supported_actions", ()) for a in actions))
        if farm_live:
            if stop != context.observation.get("return_point"):
                ambiguities.append("Use the visibly confirmed farmhouse entrance return point.")
            actions = [replace(action, parameters={**action.parameters, "capability_status": "requires_runtime_validation",
                               "farm_contract": FARM_CONTRACT},
                               preconditions=tuple(item for item in action.preconditions if item != "live_perception_and_input_not_yet_available"))
                       for action in actions]
        if live and watering_only and not farm_live:
            initial_ids = set(context.observation.get("initial_target_ids", ()))
            requested_ids = {identity for action in actions for identity in action.target_ids}
            if not initial_ids or requested_ids != initial_ids:
                ambiguities.append("The watering contract covers all initially planted crops. Review the complete initial set; a narrower live task is not supported.")
            if limits.get("stop_time") is not None or limits.get("maximum_seeds") is not None:
                unsupported.append("Clock and seed limits are unavailable for live watering; remove them before review.")
            if stop != context.observation.get("return_point"):
                ambiguities.append("Use the visibly confirmed farmhouse entrance return point.")
            actions = [replace(action, parameters={**action.parameters, "capability_status": "requires_runtime_validation",
                       "watering_contract": "initial-planted-set/v1"},
                       preconditions=tuple(item for item in action.preconditions if item != "live_perception_and_input_not_yet_available"))
                       for action in actions]
        eligibility = "requires_runtime_validation" if farm_live or live and watering_only else "unavailable_live"
        explanation = ("Review the ordered selected targets, owned items, dependencies, limits and farmhouse return. Each action requires fresh visible eligibility and reconciled postconditions; interruptions retain partial work and require new review."
                       if farm_live else "Review every initially planted crop and the farmhouse return point. Start requires fresh Stardew authority; focusing chat pauses game input."
                       if live and watering_only else
                       "Live watering requires verified disposable setup and automatic complete-set perception. Harvest, planting, clearing and combined routines remain unavailable until B4.")
        return AdapterProposal(
            normalized_intent="farm_routine", requested_objective=current.requested_objective if current else text,
            actions=tuple(actions), base_task_id=FARM_TASK_ID,
            ambiguities=tuple(dict.fromkeys(ambiguities)), unsupported_parts=tuple(dict.fromkeys(unsupported)),
            protected_choices=tuple(dict.fromkeys(protected)), resource_limits=limits,
            stop_point=stop, effective_boundary="before_next_farm_action",
            execution_eligibility=eligibility, evidence_status="fixture_only" if fixture else "proposal_only",
            fallback_explanation=explanation,
            change_summary=tuple(changes) or ("Update the proposed farm routine limits.",),
            changed_scopes=("farm_routine",),
        )
