"""Supported Mario traversal policy shared by planning and runtime validation.

This contract describes implemented primitives, not accepted route evidence or
live authorization. Those remain owned by the route registry and runtime.
"""

from dataclasses import dataclass
from types import MappingProxyType

BASE_ROUTE_ID = "world_8_finish_game"
OPENING_BOUNDARY = "world_1_1_opening"
SUPPORTED_STOP_POINTS = ("world_1_1_opening_end", "world_1_1_exit", "full_route")
SUPPORTED_SPEEDS = (1, "turbo")


@dataclass(frozen=True)
class Traversal:
    primitive_id: str
    stop_points: tuple[str, ...]


TRAVERSALS = MappingProxyType({
    "default": Traversal("world_1_1_default_v1", SUPPORTED_STOP_POINTS),
    "opening_hop": Traversal("world_1_1_opening_hop_v1", ("world_1_1_opening_end",)),
})
PRIMITIVE_PATHS = MappingProxyType({
    traversal.primitive_id: path for path, traversal in TRAVERSALS.items()
})


def validate_traversal(path: str, stop: str) -> None:
    if path not in TRAVERSALS:
        raise ValueError("Unsupported Mario traversal primitive")
    if stop not in SUPPORTED_STOP_POINTS:
        raise ValueError("Unsupported Mario stop point")
    if stop not in TRAVERSALS[path].stop_points:
        raise ValueError(
            "The opening hop is validated only to the opening stop; later traversal is unsupported"
        )
