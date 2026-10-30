"""Representative engineering geometry, not a natural-language design generator."""

import math

REGION = {
    "bounds": {"min": {"x": 0, "y": -60, "z": 0}, "max": {"x": 63, "y": -20, "z": 63}},
    "protected": [
        {"min": {"x": 48, "y": -60, "z": 8}, "max": {"x": 55, "y": -20, "z": 15}}
    ],
}


def slice_design(palette):
    cells = {}

    def put(x, y, z, name):
        if 48 <= x <= 55 and 8 <= z <= 15:
            return
        cells[x, y, z] = palette.get(name, name)

    for z in range(64):
        for x in range(64):
            height = (
                -57
                if z < 12
                else -55 + round(16 * math.exp(-((x - 51) ** 2 + (z - 50) ** 2) / 190))
            )
            for y in range(-60, height + 1):
                put(
                    x,
                    y,
                    z,
                    "stone"
                    if y < height - 1
                    else "sand"
                    if z < 20
                    else "grass_block"
                    if y == height
                    else "dirt",
                )
            if z < 12:
                for y in range(height + 1, -54):
                    put(x, y, z, "stone" if x in (0, 63) or z == 0 else "water")
    # Raised station with two rooms, stair access and a stepped roof.
    for x in range(24, 40):
        for z in range(22, 34):
            for y in range(-55, -51):
                put(x, y, z, "stone_bricks")
            for y in range(-51, -47):
                wall = x in (24, 39) or z in (22, 33) or x == 32
                door = z == 22 and x == 27 and y in (-51, -50)
                passage = x == 32 and z == 27 and y in (-51, -50)
                put(
                    x,
                    y,
                    z,
                    "air"
                    if not wall or door or passage
                    else "glass"
                    if y == -49 and z in (22, 33) and x % 4 == 1
                    else "oak_planks",
                )
            roof = -47 + min(z - 22, 33 - z) // 2
            put(x, roof, z, "spruce_planks")
            if x in (24, 39):
                for y in range(-47, roof):
                    put(x, y, z, "oak_planks")
    put(26, -51, 25, "chest")
    put(28, -51, 25, "crafting_table")
    # Door upper/lower states are explicit, not a claim of arbitrary block support.
    for y, half in [(-51, "lower"), (-50, "upper")]:
        put(
            27,
            y,
            22,
            f"oak_door[facing=north,half={half},hinge=left,open=false,powered=false]",
        )
    for z in range(18, 22):
        level = min(-52, -55 + (z - 17))
        for y in range(-55, level + 1):
            for x in range(26, 29):
                put(x, y, z, "stone_bricks")
    for x in range(10, 30):
        for z in range(5, 9):
            put(x, -54, z, "oak_planks")
    for z in range(9, 19):
        for x in range(26, 29):
            put(x, -54, z, "oak_planks")
    for x in range(5, 17):
        for z in range(20, 28):
            put(x, -54, z, "spruce_planks")
            if x % 3 == 0 or z in (20, 27):
                for y in range(-53, -50):
                    if z in (20, 27) or y == -51:
                        put(x, y, z, "oak_log")
    for x in range(44, 56):
        for z in range(40, 44):
            for y in range(-51, -48):
                put(x, y, z, "air")
    # Accessible west approach and a cut path into the ridge cavity.
    for x in range(0, 12):
        level = -60 + min(5, x // 2)
        for z in range(30, 33):
            for y in range(-60, level + 1):
                put(x, y, z, "stone_bricks")
            for y in range(level + 1, -49):
                put(x, y, z, "air")
    for x in range(32, 45):
        for z in range(40, 44):
            put(x, -52, z, "stone_bricks")
            for y in range(-51, -38):
                put(x, y, z, "air")
    # Seal the excluded column without writing inside it; fluid effects are protection too.
    for x in range(47, 57):
        for z in range(7, 17):
            if x in (47, 56) or z in (7, 16):
                for y in range(-60, -53):
                    put(x, y, z, "stone")
    # Group horizontal homogeneous runs to expose meaningful bounded fill opportunities.
    return [
        {"position": dict(zip(("x", "y", "z"), p)), "after": s}
        for p, s in sorted(
            cells.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[1], kv[0][0])
        )
    ]
