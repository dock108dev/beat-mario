"""World 1-1 sky hidden 1UP brick objective; game mechanics stay adapter-owned."""
from __future__ import annotations

import re

COMPATIBILITY = "smb3/world-1-1/sky-hidden-1up/v2"
PATH = "sky_hidden_1up"
STOP = "world_1_1_hidden_1up"
LEVEL = "world_1_page_1_node_64_32_object_1"
APPROACH = ("Jump onto the longer floor beyond the Leaf block, then run right holding B to charge P-speed, launch and tap A while steering to the "
            "hidden 1UP brick above the sky platform. Pass its right edge, descend to the clouds and "
            "jump into it from below. Reveal its 1UP mushroom, "
            "follow it and stop after observed collection or a finite partial attempt. "
            "One attempt, at most 15 seconds of gameplay and 30 seconds overall. Stop always returns control.")
REMEDY = ("Use Preparation controls or Play Mario yourself. Collect the Mushroom from the right "
          "upper question block before the first pipe. Keep Super Mario through the pipe crossing, "
          "stomp the red Koopa, carry its shell right and release it before the ground-level question block. "
          "Follow immediately and collect the Super Leaf before it falls away. Bring Raccoon or Tanooki Mario to the grounded early runway "
          "after the first pipe, then ask again. I will observe the form and entry before Start.")


def request(text: str) -> bool:
    return bool(re.search(r"\b(?:fly|flying|flight|soar|airborne|1[ -]?up|one[ -]?up|extra life|hidden reward)\b", text.lower()))


def target_error(text: str) -> str | None:
    value = text.lower()
    if re.search(r"\b(?:not|never|don't|do not)\s+(?:fly|collect|get|grab)", value):
        return "Flight was excluded; describe the objective you want instead."
    if re.search(r"\b(?:whistle|star|flower|coins|coin room)\b", value):
        return "This flight objective supports the World 1-1 sky hidden 1UP brick only. Which reward do you want?"
    level = re.search(r"(?:world|level)\s*(\d+)[ -](\d+)", value)
    if level and level.groups() != ("1", "1"):
        return "Flight reward gameplay currently supports World 1-1 only."
    if not re.search(r"\b(?:1[ -]?up|one[ -]?up|extra life)\b", value):
        return "Which flight reward do you mean? I support the sky hidden 1UP brick in World 1-1."
    return None


def prerequisites(observation: dict) -> dict:
    missing = []
    if not observation.get("fresh"):
        missing.append("A fresh connected game observation is required.")
    if observation.get("level_id") != LEVEL:
        missing.append("Enter World 1-1; its sky hidden 1UP brick is the supported target.")
    if observation.get("form") not in (3, 5):
        missing.append("Mario needs Raccoon or Tanooki form; small, Super and Fire Mario cannot fly.")
    if (observation.get("air") != 0 or not 400 <= (observation.get("x") or 0) <= 600
            or not 300 <= (observation.get("y") or 0) <= 430
            or observation.get("player_is_dying") != 0 or observation.get("return_map") != 0):
        missing.append("Prepare a living, grounded Mario on the early runway after the first pipe.")
    return {"ready": not missing, "missing": missing, "observed": observation,
            "remedy": REMEDY, "p_speed": "Build during the reviewed approach; launch only at observed P-meter =127."}


def reconcile(events: list[dict], *, terminal: str | None = None) -> dict:
    """Require continuous observations of the exact spawned mushroom and its hit popup.

    Life increments are descriptive only. Collection requires the game-owned
    1UP hit transition (object gone + new colocated 1UP popup), excluding other
    objects/rewards and counter discontinuities. Coin rollover cannot prove it.
    """
    samples, uncertain = {}, False
    for row in events:
        if row.get("event") != "flight_observation":
            continue
        try:
            keys = ("frame", "x", "y", "lives", "coins", "level_coins", "dying", "form",
                    "p_meter", "flight_timer", "slot", "object_state", "object_id", "object_x", "object_y", "popup")
            sample = {key: int(row[key]) for key in keys}
            if (not 0 <= sample['coins'] < 100 or not 0 <= sample['lives'] <= 99
                    or sample['dying'] not in (0, 1) or not 0 <= sample['level_coins'] <= 255):
                raise ValueError("invalid counter")
            if sample['frame'] in samples and samples[sample['frame']] != sample:
                uncertain = True
            samples[sample['frame']] = sample
        except (KeyError, TypeError, ValueError):
            uncertain = True
    previous, revealed, collected, flight, area = None, False, False, False, False
    coin_lives = life_changes = 0
    pending_coins = []
    for _, row in sorted(samples.items()):
        flight |= row['flight_timer'] > 0 and row['form'] in (3, 5) and row['y'] < 300
        area |= 1400 <= row['x'] <= 1490 and row['y'] <= 208
        # Slot is latched only when a new 1UP first emerges from the target
        # sky brick; unrelated rewards are not this target.
        revealed |= row['slot'] >= 1 and row['object_id'] == 11 and row['object_state'] > 0
        if previous:
            delta = row['level_coins'] - previous['level_coins']
            continuous = row['frame'] == previous['frame'] + 1
            hud_delta = (row['coins'] - previous['coins']) % 100
            valid = continuous and 0 <= delta <= 1 and hud_delta <= 1
            if valid:
                if delta:
                    pending_coins.append(row['frame'])
                if hud_delta:
                    if pending_coins:
                        pending_coins.pop(0)
                    else:
                        valid = False
                valid &= len(pending_coins) <= 1 and all(row['frame'] - frame <= 4 for frame in pending_coins)
            uncertain |= not valid
            coin_lives += int(valid and hud_delta == 1 and previous['coins'] == 99)
            life_changes += row['lives'] - previous['lives']
            # A new matching popup accompanying removal is the game's hit
            # receipt. Removal alone could be despawning; a popup alone could
            # come from another enemy/reward. Life accounting must also fit.
            if (valid and previous['slot'] >= 1 and row['slot'] == previous['slot']
                    and previous['object_id'] == row['object_id'] == 11
                    and previous['object_state'] > 0 and row['object_state'] == 0
                    and previous['popup'] == 0 and row['popup'] == 1
                    and previous['dying'] == row['dying'] == 0
                    and abs(previous['x'] - previous['object_x']) <= 24
                    and abs(previous['y'] - previous['object_y']) <= 32):
                collected = True
        previous = row
    # Game awards popup lives later; accept only a complete counter explanation
    # when they have arrived, or the specific hit receipt before its award.
    uncertain |= bool(pending_coins)
    uncertain |= life_changes not in (coin_lives, coin_lives + int(collected)) or terminal == 'death'
    confirmed = collected and not uncertain
    return {"compatibility": COMPATIBILITY, "flight_observed": flight, "area_reached": area,
            "reward_revealed": revealed, "reward_collected": True if confirmed else None if uncertain else False,
            "accounting_uncertain": uncertain or not samples, "life_change": life_changes,
            "coin_rollover_lives": coin_lives, "status": "success" if confirmed else
            "interrupted" if terminal in ("reclaimed", "stopped") else "uncertain" if uncertain or not samples else "partial" if flight or area or revealed else "failed",
            "stop_reason": terminal, "samples": len(samples)}


def report(result: dict) -> str:
    return (f"Sky hidden 1UP: {result['status']}. Flight {'observed' if result['flight_observed'] else 'unverified'}; "
            f"area {'reached' if result['area_reached'] else 'unverified'}; mushroom "
            f"{'revealed' if result['reward_revealed'] else 'unverified'}; collection "
            f"{'confirmed by the mushroom hit receipt' if result['reward_collected'] is True else 'unconfirmed'}. "
            f"Life change {result['life_change']}; coin-rollover lives {result['coin_rollover_lives']}. "
            f"Stopped because {result['stop_reason'] or 'still pursuing'}. Reaching or revealing is not collection.")


def knowledge(history: list[dict], cartridge: str | None) -> dict:
    rows = [row for row in history if cartridge and row.get('cartridge_sha256') == cartridge
            and row.get('initial_plan', {}).get('flight_compatibility') == COMPATIBILITY
            and row.get('flight_result')]
    return {"compatibility": COMPATIBILITY, "attempts": len(rows),
            "confirmed_collections": sum(row['flight_result']['reward_collected'] is True for row in rows),
            "last_result": rows[0]['flight_result'] if rows else None,
            "compatibility_pending": not bool(cartridge)}
