"""Finite capability registry. Profiles select implementations, never predicates/code."""
from types import MappingProxyType

IMPLEMENTED = MappingProxyType({
    "strict-integer/v1": "detector",
    "unique-text/v1": "detector",
    "text-click/v1": "skill",
    "exact-deltas/v1": "verifier",
})


def validate_capabilities(profile):
    from smb3_agent.game_profiles import ProfileError
    if (len(profile.capabilities) != len(set(profile.capabilities))
            or set(profile.capabilities) != set(IMPLEMENTED)):
        raise ProfileError("Unknown, missing or unimplemented capability contract")
    for sensor in profile.sensors:
        if sensor.detector_id != "strict-integer/v1":
            raise ProfileError("Unknown integer detector version")
    for skill in profile.skills:
        if (skill.detector_id, skill.skill_contract, skill.verifier_contract) != (
                "unique-text/v1", "text-click/v1", "exact-deltas/v1"):
            raise ProfileError("Unsupported skill detector or verifier contract")


def exact_delta_verification(before, after, deltas):
    """All observed resources must reconcile; unknown/extra facts cannot complete."""
    if (not isinstance(before, dict) or not isinstance(after, dict)
            or set(before) != set(after) or set(before) != set(dict(deltas))
            or any(type(v) is not int for v in (*before.values(), *after.values()))):
        return False
    return after == {key: before[key]+delta for key, delta in deltas}
