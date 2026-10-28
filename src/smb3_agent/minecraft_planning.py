"""Model-facing contracts and pure Minecraft context/movement transformations.

This module performs no I/O and owns no session authority. The chat coordinator
captures current inputs and validates authority before submitting any action.
"""

from collections import Counter
from copy import deepcopy
import json
import math

from smb3_agent.minecraft_goals import identity


def schema(properties):
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


TEXT = {"type": "string", "maxLength": 1400}
INTENT = schema(
    {
        "kind": {
            "type": "string",
            "enum": ["question", "goal", "replace", "stop", "clarify", "unavailable"],
        },
        "reply": TEXT,
    }
)
PLAN = schema(
    {
        "action": {
            "type": "string",
            "enum": [
                "move",
                "follow",
                "remember",
                "return",
                "gather",
                "build",
                "craft",
                "protect",
                "visit",
                "clarify",
                "unavailable",
            ],
        },
        "reply": TEXT,
        "direction": {
            "type": "string",
            "enum": [
                "north",
                "south",
                "east",
                "west",
                "forward",
                "back",
                "left",
                "right",
                "player",
                "home",
                "none",
            ],
        },
        "distance": {"type": "integer", "minimum": 0, "maximum": 30},
        "player": {"type": "string", "maxLength": 32},
        "remember": {"type": "string", "maxLength": 40},
        "return_place": {"type": "string", "maxLength": 40},
        "resource": {
            "type": "string",
            "enum": [
                "any_log",
                "oak_log",
                "birch_log",
                "spruce_log",
                "jungle_log",
                "acacia_log",
                "dark_oak_log",
                "mangrove_log",
                "cherry_log",
                "pale_oak_log",
                "none",
            ],
        },
        "quantity": {"type": "integer", "minimum": 0, "maximum": 32},
        "quantity_mode": {"type": "string", "enum": ["additional", "total"]},
        "protect_place": {"type": "string", "maxLength": 40},
        "protect_radius": {"type": "integer", "minimum": 0, "maximum": 32},
    }
)
STRUCTURE = schema(
    {
        "width": {"type": "integer", "minimum": 3, "maximum": 7},
        "depth": {"type": "integer", "minimum": 3, "maximum": 7},
        "height": {"type": "integer", "minimum": 2, "maximum": 4},
        "material": {
            "type": "string",
            "enum": [
                n + "_planks"
                for n in (
                    "oak",
                    "birch",
                    "spruce",
                    "jungle",
                    "acacia",
                    "dark_oak",
                    "mangrove",
                    "cherry",
                    "pale_oak",
                )
            ],
        },
        "doorway": {"type": "string", "enum": ["north", "south", "east", "west"]},
        "windows": {"type": "boolean"},
        "site_place": {"type": "string", "maxLength": 40},
        "offset": schema(
            {
                k: {"type": "integer", "minimum": -24, "maximum": 24}
                for k in ("x", "y", "z")
            }
        ),
        "revise": {"type": "boolean"},
        "relocate": {"type": "boolean"},
        "remaining_only": {"type": "boolean"},
        "allow_removal": {"type": "boolean"},
        "flexible_site": {"type": "boolean"},
    }
)
BUILD_PLAN = deepcopy(PLAN)
BUILD_PLAN["properties"]["structure"] = STRUCTURE
BUILD_PLAN["required"].append("structure")
BUILD_PLAN["properties"]["craft_item"] = {
    "type": "string",
    "enum": ["none", "stick", "crafting_table"]
    + [
        n + "_planks"
        for n in (
            "oak",
            "birch",
            "spruce",
            "jungle",
            "acacia",
            "dark_oak",
            "mangrove",
            "cherry",
            "pale_oak",
        )
    ]
    + [m + "_" + t for m in ("wooden", "stone") for t in ("pickaxe", "axe", "shovel")],
}
BUILD_PLAN["properties"]["craft_quantity"] = {
    "type": "integer",
    "minimum": 1,
    "maximum": 1000000,
}
BUILD_PLAN["properties"]["hand_only"] = {"type": "boolean"}
BUILD_PLAN["required"] += ["craft_item", "craft_quantity", "hand_only"]
BUILD_PLAN["properties"]["structure_name"] = {"type": "string", "maxLength": 40}
BUILD_PLAN["properties"]["preference"] = {"type": "string", "maxLength": 400}
BUILD_PLAN["required"] += ["structure_name", "preference"]
IDLE_PLAN = deepcopy(BUILD_PLAN)
IDLE_PLAN["properties"]["action"]["enum"] += ["question", "stop"]

RULES = """Minecraft 1.21.4 practice companion. Answer naturally and concisely from observations.
Distinguish a question (even during active play) from a new goal or replacement, Stop,
ambiguity, and unsupported requests. Questions NEVER change gameplay. Supported: walk
up to 30 blocks in cardinal/bot-relative directions, to saved places, or toward
an observed player; follow an observed player for up to 25 seconds within 32 blocks.
Do not claim already executed actions. No teleporting. Building now supports bounded wooden shelters through action=build.
Visit an observed nearby tree with action=visit and its resource type; this only approaches it.
Supported multi-step actions: remember current spot (remember=name); return to saved
place (return_place=name); gather 1–32 common logs (resource=exact log name or any_log,
quantity, quantity_mode=additional by default, total only when explicitly requested).
Gather may remember the current spot and return to it in the same goal. Use action=gather.
Set hand_only=true when the user requests hand gathering, otherwise false. Tools are selected from inventory; logs can validly use hand. Never call tools yourself.
Protected areas are cylinders around explicitly named saved places (protect_place,
protect_radius), retained for this world; action=protect can save them without gathering.
If 'those trees', 'by the house', or a boundary is ambiguous, clarify which saved place
and radius the user means BEFORE any work. Never invent a protected boundary.
A new remembered current spot can anchor protection. All unused string fields are empty
except resource=none, quantity=0, quantity_mode=additional, protect_radius=0.
Use observed resource variants; unavailable resources give honest partial outcomes.
Gathering is a multi-skill goal with 240 seconds/160 child actions/3 failures/32-block bounds.
Craft via action=craft with craft_item and craft_quantity (target inventory total). Encode the requested total exactly, including totals above 64; runtime refuses unsupported totals above 64. Never silently clamp or substitute a smaller quantity. Supported common planks, sticks, tables and wooden/stone axes, pickaxes, shovels. Uses structure.material wood variant. Dependencies and workstations are resolved from actual game data. Default unused craft_item=none, craft_quantity=1.
Saved places must match current world and dimension; movement to saved places uses return.
Ordinary questions about progress do not replace a goal.
If 'me' is ambiguous ask which observed player. Player names must come from entities,
not just the player roster. Unknown landmarks need clarification. History is context,
not permission to resume. Only the latest user request grants intent. Never use tools.
Construction: action=build composes gathering logs, crafting planks and building walls/roof.
Use structure width/depth 3–7, wall height 2–4, material common wood planks, cardinal doorway,
windows boolean, site_place (saved place or empty for current position), integer offset x/y/z.
Set flexible_site=true for "near"/"nearby" requests to allow a bounded clear-site search within twelve blocks of the chosen origin and one block vertically; false for exact coordinates/sites.
Defaults for a small shelter: 3x3, height 2, oak, no windows. Choose a nearby level site
with offset to avoid standing in the walls; runtime inspects terrain before modifying it.
If doorway faces me and no human entity is observed, clarify cardinal direction BEFORE work.
For a revision set revise=true, retain unchanged parameters from construction context.
relocate=false keeps the prior origin; true uses a new site_place/current position plus offset.
Changes to material require clarification about remaining work versus replacing completed blocks;
explicit 'remaining' means remaining_only=true. Set allow_removal=true ONLY when the latest user explicitly permits removal/replacement of completed construction blocks. Default false; changing dimensions or doorway alone does not grant removal. Explain required removal when needed. Never imply refunds.
structure_name selects a saved structure by exact name for revisions, or names a new build.
Use action=remember with structure_name to name the latest validated structure (remember empty).
Saved structure facts are historical, require inspection before action; do not claim current access.
For explicit user preferences use action=remember, preference=their preference; otherwise preference="".
Use empty structure_name when no name is requested. Never invent remembered facts.
An observed_site_offer is a read-only inspected suggestion, not permission. Only on explicit user acceptance build it: use the offered dimensions/material/doorway/windows, site_place="", offset = offered origin minus floor(current position), flexible_site=false. Runtime revalidates it before execution. Otherwise ask before changing intent.
Supply structure defaults for non-build plans; those fields are unused then.
When idle, interpret and propose in one response: use action=question for ordinary questions and action=stop for Stop; neither grants gameplay authority.
For a plan use one direction plus distance (default 10 if unspecified). Follow uses
player and direction=player. Return clarify/unavailable when a destination is unknown.
"""


def build_context(
    text,
    state,
    *,
    memory,
    opened_at_ms,
    goal,
    active_goal_id,
    site_offer,
    construction,
    places,
    protections,
    home,
    messages,
    events,
    goal_progress,
):
    """Format observed and historical facts without granting action authority."""

    def outcome(e):
        return {
            k: (v[:160] if isinstance(v, str) and k in {"request", "reason"} else v)
            for k, v in e.items()
            if k not in {"world", "placed", "spec"}
        }

    context = {
        "instructions": RULES
        + " Label saved structures as historical unless a goal outcome in current_session_outcomes verifies work in this session. Distinguish completed, partial and canceled outcomes; never credit historical construction to this session. While a goal is active, historical outcomes or a site offer with a different goal_id are NOT results of that active goal. If current checks have not returned, say they are still underway.",
        "current_session_outcomes": [
            outcome(e)
            for e in memory.get("outcomes", [])
            if e.get("at_ms", 0) >= opened_at_ms
            and e.get("world")
            == [
                state.get("world_id"),
                state.get("dimension"),
                state.get("game_version"),
            ]
        ][-40:],
        "request": text,
        "observations": {**state, "resources": state.get("resources", [])[:24]},
        "active_goal": goal,
        "active_goal_id": active_goal_id,
        "observed_site_offer": site_offer
        if site_offer
        and site_offer["world"]
        == [
            state.get("world_id"),
            state.get("dimension"),
            state.get("game_version"),
        ]
        else None,
        "construction": (
            {
                "world": construction["world"],
                "spec": {
                    k: v
                    for k, v in construction["spec"].items()
                    if k not in {"allow_removal", "revise", "relocate"}
                },
                "placed": len(construction["placed"]),
                "materials_placed": dict(
                    Counter(c["item"] for c in construction["placed"])
                ),
            }
            if construction
            and construction["world"]
            == [
                state.get("world_id"),
                state.get("dimension"),
                state.get("game_version"),
            ]
            else None
        ),
        "named_places": {
            k: v
            for k, v in places.items()
            if v["world"]
            == [
                state.get("world_id"),
                state.get("dimension"),
                state.get("game_version"),
            ]
        },
        "protected_areas": protections.get(
            json.dumps(
                [
                    state.get("world_id"),
                    state.get("dimension"),
                    state.get("game_version"),
                ]
            ),
            [],
        ),
        "saved_structures": [
            {
                "name": r.get("name", ""),
                "spec": {
                    k: v
                    for k, v in r["spec"].items()
                    if k not in {"allow_removal", "revise", "relocate"}
                },
                "placed": len(r["placed"]),
                "outcome": r.get("outcome"),
                "status": "historical; inspect before reuse",
            }
            for r in memory["structures"].values()
            if r["world"]
            == [
                state.get("world_id"),
                state.get("dimension"),
                state.get("game_version"),
            ]
        ][-20:],
        "preferences": memory["preferences"].get(
            json.dumps(
                [
                    state.get("world_id"),
                    state.get("dimension"),
                    state.get("game_version"),
                ]
            ),
            [],
        ),
        "resource_constraints": memory.get("resource_constraints", {}).get(
            json.dumps(
                [
                    state.get("world_id"),
                    state.get("dimension"),
                    state.get("game_version"),
                ]
            ),
            [],
        )[-6:],
        "historical_outcomes": [
            outcome(e)
            for e in memory.get("outcomes", [])
            if e["world"]
            == [
                state.get("world_id"),
                state.get("dimension"),
                state.get("game_version"),
            ]
        ][-3:],
        "session_start": home,
        "recent_conversation": [
            {"role": m["role"], "text": m["text"][:1000]} for m in messages[-10:]
        ],
        "recent_results": [
            {
                **{
                    k: v
                    for k, v in e.items()
                    if k
                    in {
                        "kind",
                        "at_ms",
                        "reason",
                        "complete",
                        "shortfall",
                        "inventory_gains",
                        "inventory_losses",
                        "failures",
                        "goal_id",
                    }
                },
                "placed_count": len(e.get("placed", [])),
            }
            for e in events
            if e["kind"]
            in {
                "goal_outcome",
                "construction_outcome",
                "craft_outcome",
                "goal_recovery",
                "action_result",
            }
        ][-3:],
        "goal_progress": goal_progress,
    }
    # The full durable evidence remains on disk. Bound explanatory history,
    # never authority, protections, observed state or accepted geometry.
    context["history_omitted"] = {}
    for field in (
        "recent_conversation",
        "recent_results",
        "historical_outcomes",
        "resource_constraints",
        "current_session_outcomes",
    ):
        while context[field] and len(json.dumps(context)) > 29000:
            context[field].pop(0)
            context["history_omitted"][field] = (
                context["history_omitted"].get(field, 0) + 1
            )
    context["instructions"] += (
        " If history_omitted is nonempty, explicitly limit recaps to retained outcomes; do not claim an exhaustive session summary."
    )
    return context


def distance(a, b):
    return math.sqrt(sum((a[k] - b[k]) ** 2 for k in ("x", "y", "z")))


def resolve_movement(plan, state, *, places, home):
    p = state["position"]
    entities = {e["name"]: e for e in state.get("entities", [])}
    if plan["action"] == "follow" or plan["direction"] == "player":
        entity = entities.get(plan["player"])
        if not entity or distance(p, entity["position"]) > 32:
            raise ValueError(
                "That player is not observed within 32 blocks. Move closer or name a visible player."
            )
        if plan["action"] == "follow":
            return {
                "action": "follow",
                "player": plan["player"],
                "entity_id": entity["id"],
                "duration_ms": 25000,
            }
        target = entity["position"]
    elif plan["direction"] == "home":
        place = places.get("home")
        if place and place["world"] != identity(state):
            raise ValueError("Home belongs to another world/dimension.")
        target = place["position"] if place else home
    else:
        d = plan["distance"]
        if not 1 <= d <= 30:
            raise ValueError("Choose a walking distance between 1 and 30 blocks.")
        yaw = state.get("yaw", 0)
        vectors = {
            "north": (0, -1),
            "south": (0, 1),
            "east": (1, 0),
            "west": (-1, 0),
            "forward": (-math.sin(yaw), -math.cos(yaw)),
            "back": (math.sin(yaw), math.cos(yaw)),
            "left": (math.cos(yaw), -math.sin(yaw)),
            "right": (-math.cos(yaw), math.sin(yaw)),
        }
        if plan["direction"] not in vectors:
            raise ValueError("Please name a direction, home, or an observed player.")
        x, z = vectors[plan["direction"]]
        target = {"x": p["x"] + d * x, "y": p["y"], "z": p["z"] + d * z}
    if distance(p, target) > 32:
        raise ValueError(
            "Destination is beyond this session's 32-block movement limit."
        )
    result = {"action": "move", "target": target}
    if plan["direction"] not in {"home", "player"}:
        result["surface_destination"] = True
    return result
