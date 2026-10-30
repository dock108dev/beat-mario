"""Pure, terrain-bound architecture composition; no execution authority or I/O.

Catalog assemblies describe their real native/decorative capabilities. Unknown
inventory remains visible and blocks execution, rather than disappearing from a plan.
"""

from copy import deepcopy
import re

from smb3_agent.minecraft_terrain import digest

MATERIALS = {
    "glass": {
        "floor": "stone_bricks",
        "wall": "glass",
        "roof": "glass",
        "fabric": "white_wool",
    },
    "warm": {
        "floor": "oak_planks",
        "wall": "oak_planks",
        "roof": "spruce_planks",
        "fabric": "white_wool",
    },
    "coastal": {
        "floor": "oak_planks",
        "wall": "white_wool",
        "roof": "oak_planks",
        "fabric": "white_wool",
    },
    "natural": {
        "floor": "spruce_planks",
        "wall": "spruce_planks",
        "roof": "spruce_planks",
        "fabric": "white_wool",
    },
    "industrial": {
        "floor": "stone_bricks",
        "wall": "stone_bricks",
        "roof": "spruce_planks",
        "fabric": "white_wool",
    },
}
CATALOG = {
    "cooking corner": ("native cooking and storage", (4, 2, 3)),
    "awning": ("decorative", (5, 4, 4)),
    "stall": ("decorative", (5, 4, 4)),
    "bench": ("decorative", (3, 1, 2)),
    "table": ("decorative", (3, 2, 2)),
    "shelf": ("decorative", (3, 1, 3)),
    "radio-like console": ("decorative", (3, 2, 2)),
    "supply crate cluster": ("decorative", (3, 2, 2)),
    "bollard": ("decorative", (1, 1, 2)),
    "wreck rib": ("decorative", (1, 7, 4)),
    "counter": ("decorative", (3, 1, 2)),
    "lamppost": ("native lighting", (1, 1, 4)),
    "pantry shelves": ("decorative", (3, 1, 3)),
    "planter": ("decorative", (3, 2, 2)),
    "static wheel": ("decorative", (1, 7, 7)),
    "signpost": ("decorative marker; labels in project review", (3, 1, 3)),
}
ALIASES = {
    "static decorative wheel": "static wheel",
    "radio": "radio-like console",
    "shelves": "shelf",
    "crate": "supply crate cluster",
}
NATIVE = {"doors", "chests", "beds", "crafting table", "lamps"}


def state(palette, name, **properties):
    if name not in palette:
        raise ValueError(f"Native block unavailable: {name}")
    value = palette[name]
    props = dict(re.findall(r"(\w+)=(\w+)", value))
    props.update({k: str(v).lower() for k, v in properties.items()})
    return name + (
        "[" + ",".join(f"{k}={v}" for k, v in sorted(props.items())) + "]"
        if props
        else ""
    )


def assembly(kind, material):
    """Reusable local cells; rotation is handled by the enclosing composition."""
    kind = ALIASES.get(kind.lower(), kind.lower())
    if kind not in CATALOG:
        raise ValueError(f"Unsupported object: {kind}")
    w, d, h = CATALOG[kind][1]
    cells = {}

    def put(x, y, z, block):
        cells[x, y, z] = block

    wood = material["floor"]
    if kind == "cooking corner":
        for x in range(4):
            for z in range(2):
                put(x, 0, z, wood)
        put(0, 1, 0, "furnace")
        put(2, 1, 0, "chest")
    elif kind in {"awning", "stall"}:
        for x in range(w):
            for z in range(d):
                put(x, h - 1, z, material["fabric"])
        for x in (0, w - 1):
            for z in (0, d - 1):
                for y in range(h - 1):
                    put(x, y, z, wood)
        if kind == "stall":
            for x in range(1, w - 1):
                put(x, 0, d - 1, wood)
    elif kind in {"shelf", "pantry shelves"}:
        for x in range(w):
            for y in (0, 2):
                put(x, y, 0, wood)
    elif kind == "static wheel":
        # A flush decorative wheel must contrast with its facade in every palette.
        accent = (
            "oak_planks" if material["roof"] == material["wall"] else material["roof"]
        )
        for z in range(7):
            for y in range(7):
                r = (z - 3) ** 2 + (y - 3) ** 2
                if 5 <= r <= 12 or z == 3 or y == 3:
                    put(0, y, z, accent)
    elif kind == "wreck rib":
        for z in range(d):
            put(0, abs(z - 3), z, material["roof"])
    elif kind in {"bollard", "lamppost", "signpost"}:
        for y in range(h - 1):
            put(w // 2, y, 0, wood)
        if kind == "lamppost":
            put(0, h - 1, 0, "glowstone")
        elif kind == "signpost":
            for x in range(w):
                put(x, h - 1, 0, material["fabric"])
    else:
        for x in range(w):
            for z in range(d):
                put(x, 0, z, wood if kind != "planter" else "dirt")
        if kind == "bench":
            for x in range(w):
                put(x, 1, 0, material["roof"])
        if kind == "radio-like console":
            put(1, 1, 0, "glass")
        if kind == "supply crate cluster":
            put(0, 1, 0, material["roof"])
    return cells


def expanded_rooms(rooms):
    result = []
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
    for room in rooms:
        match = re.match(r"(\d+|one|two|three|four|five|six) (.+)", room)
        if match:
            count = int(match[1]) if match[1].isdigit() else words[match[1]]
            if count > 12:
                raise ValueError("Room count exceeds supported composition")
            result.extend(f"{match[2]} {i + 1}" for i in range(count))
        else:
            result.append(room)
    return result


def compile_architecture(
    design, terrain, palette, *, selected=None, material=None, existing=None
):
    if design.get("planning", {}).get("state", "ready") != "ready":
        raise ValueError("Resolve the design checklist before architecture review")
    if terrain.get("digest") != digest(
        {k: v for k, v in terrain.items() if k != "digest"}
    ):
        raise ValueError("Terrain manifest integrity changed")
    material_name = material or design["palette"]
    if material_name not in MATERIALS:
        raise ValueError("Choose a supported architecture material")
    materials = MATERIALS[material_name]
    parts, unsupported, dependencies = [], [], []
    junction_components = []
    sea = terrain["sea_level"]
    occupied = {}
    for component in design["components"]:
        name, kind = component["name"], component["kind"]
        if selected and name != selected:
            continue
        if (
            kind == "decoration"
            and "junction"
            in component.get("requirement_source", {}).get("quote", "").lower()
        ):
            junction_components.append(component)
            continue
        objects = list(component.get("objects", []))
        if (
            "cooking corner"
            in component.get("requirement_source", {}).get("quote", "").lower()
            and "cooking corner" not in objects
        ):
            objects.append("cooking corner")
        if (
            kind == "decoration"
            and "signpost"
            in component.get("requirement_source", {}).get("quote", "").lower()
            and "signpost" not in objects
        ):
            objects.append("signpost")
        if (
            kind
            not in {
                "building",
                "pavilion",
                "platform",
                "tower",
                "dock",
                "wreck",
                "decoration",
            }
            and not objects
        ):
            continue
        reservation = terrain["reservations"].get(name)
        if not reservation:
            dependencies.append(f"{name}: requires a reviewed terrain reservation")
            continue
        x0, z0, w, d = reservation["box"]
        if [x0, z0, w, d] != component["box"][:4]:
            dependencies.append(f"{name}: footprint differs from reviewed terrain")
            continue
        if not (3 <= w <= 64 and 3 <= d <= 64):
            unsupported.append(f"{name}: architecture footprints must be 3–64 blocks")
            continue
        turn = component.get("turn", 0)
        lw, ld = (d, w) if turn % 2 else (w, d)
        h = component["box"][5]
        level = reservation["level"]
        floor = sea + level
        cells, rooms, inventory, walks = {}, [], [], []
        extensions = []

        def world(x, y, z):
            if turn == 0:
                a, b = x, z
            elif turn == 1:
                a, b = ld - 1 - z, x
            elif turn == 2:
                a, b = lw - 1 - x, ld - 1 - z
            else:
                a, b = z, lw - 1 - x
            return (
                terrain["origin"][0] + x0 + a,
                floor + y,
                terrain["origin"][1] + z0 + b,
            )

        def put(x, y, z, block, *, exterior=False, **props):
            if not exterior and not (0 <= x < lw and 0 <= z < ld):
                raise ValueError(
                    f"{name}: assembly does not fit its reviewed footprint"
                )
            if "facing" in props:
                directions = ["north", "east", "south", "west"]
                props["facing"] = directions[
                    (directions.index(props["facing"]) + turn) % 4
                ]
            pos = world(x, y, z)
            if (
                not terrain["region"]["bounds"]["min"]["y"]
                <= pos[1]
                <= terrain["region"]["bounds"]["max"]["y"]
            ):
                raise ValueError(f"{name}: height exceeds reviewed region")
            if any(
                not terrain["region"]["bounds"]["min"][axis]
                <= pos[i]
                <= terrain["region"]["bounds"]["max"][axis]
                for i, axis in enumerate(("x", "y", "z"))
            ):
                raise ValueError(f"{name}: access extension exceeds reviewed region")
            cells[pos] = state(palette, block, **props)

        def fill(xa, xb, ya, yb, za, zb, block):
            for y in range(ya, yb + 1):
                for z in range(za, zb + 1):
                    for x in range(xa, xb + 1):
                        put(x, y, z, block)

        def point(x, y, z):
            return dict(zip(("x", "y", "z"), world(x, y, z)))

        solid_building = kind in {
            "building",
            "pavilion",
            "platform",
            "tower",
            "dock",
            "wreck",
        }
        if solid_building:
            # A full level deck plus supports uses only the reviewed footprint.
            fill(0, lw - 1, 0, 0, 0, ld - 1, materials["floor"])
            for x in range(lw):
                for z in range(ld):
                    wx, _, wz = world(x, 0, z)
                    ground = terrain["field"]["height"][wz - terrain["origin"][1]][
                        wx - terrain["origin"][0]
                    ]
                    if ground > level:
                        dependencies.append(
                            f"{name}: floor intersects terrain at {wx},{wz}; review terrain dependency"
                        )
                    if x in (0, lw - 1) or z in (0, ld - 1):
                        for y in range(ground - level + 1, 0):
                            put(x, y, z, "stone_bricks")
        requested_rooms = expanded_rooms(component.get("rooms", []))
        text = " ".join(
            [
                component.get("detail", ""),
                component.get("requirement_source", {}).get("quote", ""),
            ]
        ).lower()
        storeys = component.get("constraints", {}).get("storeys", 1)
        loft = "loft" in text or any("loft" in r for r in requested_rooms)
        if loft:
            storeys = max(2, storeys)

        def roof_height(x):
            if "steep" in text:
                return max(4, h - 1 - int(abs(x - (lw - 1) / 2) / 2))
            if "asymmetric" in text and x >= 2 * lw // 3:
                return h - 2
            return h - 1

        if kind == "building":
            if h < 5 or (storeys == 2 and (h < 9 or ld < 12 or lw < 12)) or storeys > 2:
                raise ValueError(
                    f"{name}: rooms/stairs need a larger reviewed envelope"
                )
            fill(0, lw - 1, 1, h - 1, 0, ld - 1, "air")
            for y in range(1, h - 1):
                for x in range(lw):
                    for z in (0, ld - 1):
                        if y >= roof_height(x):
                            continue
                        put(
                            x,
                            y,
                            z,
                            "glass"
                            if y % 5 in (2, 3) and 1 < x < lw - 2
                            else materials["wall"],
                        )
                for z in range(1, ld - 1):
                    for x in (0, lw - 1):
                        if y >= roof_height(x):
                            continue
                        put(
                            x,
                            y,
                            z,
                            "glass"
                            if y % 5 in (2, 3) and 1 < z < ld - 2
                            else materials["wall"],
                        )
            upper = 4 if loft else 5
            floor_levels = [0, upper] if storeys == 2 else [0]
            if storeys == 2:
                left_edge, right_edge = (3, lw - 4) if loft else (1, lw - 2)
                fill(left_edge, right_edge, upper, upper, 1, ld - 2, materials["floor"])
                # Straight native stairs keep two blocks of headroom under the roof.
                stair_columns = (3,) if loft else (1, 2)
                for step in range(upper):
                    for x in stair_columns:
                        fill(
                            x,
                            x,
                            step + 1,
                            min(h - 2, step + 4),
                            step + 2,
                            step + 2,
                            "air",
                        )
                        put(
                            x,
                            step + 1,
                            step + 2,
                            "oak_stairs",
                            facing="south",
                            half="bottom",
                            shape="straight",
                            waterlogged=False,
                        )
                walks += [
                    point(stair_columns[0], 1, 1),
                    point(stair_columns[0], upper + 1, upper + 2),
                ]
            for y in floor_levels:
                these = [
                    r
                    for r in requested_rooms
                    if ("upstairs" in r or "loft" in r) == (y > 0)
                ]
                if not these:
                    these = ["upper room" if y else "main room"]
                # Central circulation corridor; partitions stop at the corridor.
                usable = lw - (8 if loft and y else 6)
                if usable < 3 and len(these) == 1 and len(floor_levels) == 1 and lw >= 5 and ld >= 5:
                    # A small one-room cabin uses its open interior; it does not
                    # need the corridor and partitions of a multi-room building.
                    rooms.append({"name": these[0], "floor": point(lw // 2, y, ld // 2),
                                  "entrance": point(lw // 2, y + 1, 0)})
                    walks.append(point(lw // 2, y + 1, ld // 2))
                    continue
                if usable // len(these) < 3:
                    raise ValueError(f"{name}: requested rooms need more width")
                for i, room in enumerate(these):
                    left = 4 + i * usable // len(these)
                    right = 4 + (i + 1) * usable // len(these) - 1
                    fill(left, right, y + 1, min(y + 3, h - 2), 4, 4, materials["wall"])
                    if i:
                        fill(
                            left,
                            left,
                            y + 1,
                            min(y + 3, h - 2),
                            5,
                            ld - 2,
                            materials["wall"],
                        )
                    fill(left + 1, left + 1, y + 1, y + 2, 4, 4, "air")
                    rooms.append(
                        {
                            "name": room,
                            "floor": point(left + 1, y, 5),
                            "entrance": point(left + 1, y + 1, 4),
                        }
                    )
                    walks.append(point(left + 1, y + 1, 7))
            # Roof profile and end walls share the same height function.
            for x in range(lw):
                roof_y = roof_height(x)
                for z in range(ld):
                    put(x, roof_y, z, materials["roof"])
            entrance_x = lw // 2
            fill(entrance_x, entrance_x + 1, 1, 3, 0, 0, "air")
            walks.append(point(entrance_x, 1, 0))
        elif kind == "pavilion":
            fill(0, lw - 1, 1, h - 2, 0, ld - 1, "air")
            fill(0, lw - 1, h - 1, h - 1, 0, ld - 1, materials["roof"])
            for x in (0, lw - 1):
                for z in (0, ld - 1):
                    fill(x, x, 1, h - 2, z, z, materials["wall"])
            rooms.append({"name": "open pavilion", "floor": point(lw // 2, 0, ld // 2)})
        elif kind == "tower":
            if lw < 9 or ld < 9 or h < 10:
                raise ValueError(
                    f"{name}: internal tower stair needs at least 9 by 9 by 10"
                )
            fill(0, lw - 1, 1, h - 1, 0, ld - 1, "air")
            for y in range(1, h - 3):
                for x in range(lw):
                    put(x, y, 0, "stone_bricks")
                    put(x, y, ld - 1, "stone_bricks")
                for z in range(ld):
                    put(0, y, z, "stone_bricks")
                    put(lw - 1, y, z, "stone_bricks")
            ring = (
                [(x, 1, "east") for x in range(1, lw - 2)]
                + [(lw - 2, z, "south") for z in range(1, ld - 2)]
                + [(x, ld - 2, "west") for x in range(lw - 2, 1, -1)]
                + [(1, z, "north") for z in range(ld - 2, 1, -1)]
            )
            for step in range(h - 4):
                x, z, facing = ring[step % len(ring)]
                put(
                    x,
                    step + 1,
                    z,
                    "oak_stairs",
                    facing=facing,
                    half="bottom",
                    shape="straight",
                    waterlogged=False,
                )
                walks.append(point(x, step + 2, z))
            fill(1, lw - 2, h - 4, h - 4, 1, ld - 2, materials["floor"])
            # Keep stair approach/headroom open through the viewing floor.
            for step in range(max(0, h - 8), h - 4):
                x, z, _ = ring[step % len(ring)]
                fill(x, x, step + 2, min(h - 2, step + 4), z, z, "air")
            for x in range(lw):
                put(x, h - 3, 0, "glass")
                put(x, h - 3, ld - 1, "glass")
            for z in range(ld):
                put(0, h - 3, z, "glass")
                put(lw - 1, h - 3, z, "glass")
            fill(0, lw - 1, h - 1, h - 1, 0, ld - 1, materials["roof"])
            put(lw // 2, h - 2, ld // 2, "glowstone")
            inventory.append(
                {
                    "type": "lamps",
                    "capability": "native lighting",
                    "position": point(lw // 2, h - 2, ld // 2),
                    "count": 1,
                }
            )
            fill(1, 1, 1, 3, 0, 0, "air")
            rooms.append(
                {"name": "lantern room", "floor": point(lw // 2, h - 4, ld // 2)}
            )
        elif kind == "wreck":
            fill(1, lw - 2, 1, h - 1, 1, ld - 2, "air")
            for x in range(lw):
                for z in (0, ld - 1):
                    put(x, 1, z, materials["roof"])
            for x in (lw // 3, 2 * lw // 3):
                for z in range(ld):
                    put(x, 1 + abs(z - ld // 2) // 2, z, materials["roof"])
            fill(lw // 2, lw // 2 + 1, 1, 2, 0, 0, "air")
            rooms.append({"name": "cargo cavity", "floor": point(lw // 2, 0, ld // 2)})
            inventory.extend(
                [{"type": "wreck rib", "capability": "decorative", "count": 2}]
            )
        if kind == "dock":
            landing_length = min(8, lw)
            for x in range(lw - landing_length, lw):
                for z in range(-1, ld + 1):
                    put(x, 0, z, materials["floor"], exterior=True)
                    if x in (lw - landing_length, lw - 1) and z in (-1, ld):
                        wx, _, wz = world(x, 0, z)
                        ground = terrain["field"]["height"][wz - terrain["origin"][1]][
                            wx - terrain["origin"][0]
                        ]
                        if ground > level:
                            dependencies.append(
                                f"{name}: landing requires terrain review"
                            )
                        for y in range(ground - level + 1, 0):
                            put(x, y, z, materials["floor"], exterior=True)
            extensions.append(
                {
                    "type": "wider landing",
                    "width": landing_length,
                    "depth": ld + 2,
                    "position": point(lw - landing_length, 0, -1),
                    "note": "One block beyond each side of the reserved walkway, inside the reviewed project region.",
                }
            )
        # Required objects are individually composable; unsupported circulation
        # requests are handled by the building geometry above.
        structural = {"internal stair", "internal stairs", "loft stairs", "railings"}
        items = []
        for obj in objects:
            item = ALIASES.get(obj.lower(), obj.lower())
            if item in structural or (item == "wreck rib" and kind == "wreck"):
                continue
            if item not in CATALOG:
                unsupported.append(f"{name}: unsupported object {obj}")
                continue
            quote = component.get("requirement_source", {}).get("quote", "").lower()
            repeated = (
                (item == "awning" and "awnings" in quote)
                or (item == "stall" and "stalls" in quote)
                or (item == "signpost" and "junctions" in quote)
            )
            count = component.get("constraints", {}).get("count", 1) if repeated else 1
            items.extend([item] * count)
        used = set()
        # Clearings may contain another named place in an older layout. Furniture
        # must not occupy that footprint, even when only one place is selected.
        other_sites = [
            site["box"]
            for other, site in terrain["reservations"].items()
            if other != name
            and next(
                (c["kind"] for c in design["components"] if c["name"] == other), ""
            )
            in {"building", "pavilion", "tower", "dock", "wreck"}
        ]
        if kind in {"terrain", "decoration"}:
            path_cells = {(x, z) for x, z, _ in terrain["field"].get("paths", [])}
            for x in range(lw):
                for z in range(ld):
                    wx, _, wz = world(x, 0, z)
                    px, pz = wx - terrain["origin"][0], wz - terrain["origin"][1]
                    if (px, pz) in path_cells or any(
                        a <= px < a + sw and b <= pz < b + sd
                        for a, b, sw, sd in other_sites
                    ):
                        used.add((x, z))
        retained = (existing or {}).get(name, {})
        retained_objects = (
            list(retained.get("objects", []))
            if retained.get("box") == component["box"]
            and retained.get("turn") == component.get("turn", 0)
            else []
        )
        for item in items:
            old_object = next(
                (
                    o
                    for o in retained_objects
                    if o["type"] == item and o.get("position")
                ),
                None,
            )
            if old_object:
                retained_objects.remove(old_object)
            local = assembly(item, materials)
            if item == "static wheel" and kind == "building":
                # A static facade assembly is visibly decorative; it never claims
                # moving machinery. Keep it inside the reviewed envelope.
                if h < 8 or ld < 9:
                    unsupported.append(f"{name}: wheel needs a taller facade")
                    continue
                for (dx, y, dz), block in local.items():
                    put(dx, y + 1, dz + 1, block)
                inventory.append(
                    {
                        "type": item,
                        "capability": CATALOG[item][0],
                        "position": point(0, 1, 1),
                        "count": 1,
                    }
                )
                continue
            ow, od, oh = CATALOG[item][1]
            margin = 1 if kind == "building" else 0
            options = [
                (x, z)
                for z in range(margin, ld - od + 1 - margin)
                for x in range(margin, lw - ow + 1 - margin)
            ]
            if old_object:
                # Stable placement is part of retained architecture: a path or
                # palette review must not move an existing container/furnishing
                # merely because an earlier first-fit position became free.
                old_pos = old_object["position"]
                options.sort(
                    key=lambda p: (
                        not (
                            world(p[0], 0, p[1])[0] == old_pos["x"]
                            and world(p[0], 0, p[1])[2] == old_pos["z"]
                        )
                    )
                )
            selected_site = next(
                (
                    (x, z)
                    for x, z in options
                    if all(
                        (x + dx, z + dz) not in used
                        for dx in range(ow + 1)
                        for dz in range(od + 1)
                    )
                    and all(
                        cells.get(world(x + dx, y + 1, z + dz), "air") == "air"
                        for dx, y, dz in local
                    )
                ),
                None,
            )
            if selected_site is None:
                unsupported.append(f"{name}: no clear placement for {item}")
                continue
            x, z = selected_site
            used.update(
                (x + dx, z + dz) for dx in range(ow + 1) for dz in range(od + 1)
            )
            base = 0
            if kind in {"terrain", "decoration"}:
                grounds = []
                for dx in range(ow):
                    for dz in range(od):
                        wx, _, wz = world(x + dx, 0, z + dz)
                        grounds.append(
                            terrain["field"]["height"][wz - terrain["origin"][1]][
                                wx - terrain["origin"][0]
                            ]
                        )
                base = max(grounds) - level
                for dx in range(ow):
                    for dz in range(od):
                        wx, _, wz = world(x + dx, 0, z + dz)
                        ground = terrain["field"]["height"][wz - terrain["origin"][1]][
                            wx - terrain["origin"][0]
                        ]
                        for y in range(ground - level + 1, base + 1):
                            put(x + dx, y, z + dz, materials["floor"])
            for (dx, y, dz), block in local.items():
                put(x + dx, y + base + 1, z + dz, block)
            inventory.append(
                {
                    "type": item,
                    "capability": CATALOG[item][0],
                    "position": point(x, base + 1, z),
                    "count": 1,
                }
            )
            if item == "cooking corner":
                inventory[-1]["parts"] = [
                    {"type": "furnace", "position": point(x, base + 2, z)},
                    {"type": "chests", "position": point(x + 2, base + 2, z)},
                ]
        unknown_native = set(component.get("native", [])) - NATIVE
        unsupported.extend(
            f"{name}: unsupported native element {v}" for v in sorted(unknown_native)
        )
        # Native placements remain explicit. Their registry states and runtime
        # interaction are qualified independently from decorative assemblies.
        for native in component.get("native", []):
            if native not in NATIVE or kind != "building":
                continue
            x, z = lw // 2, 0
            if native == "doors":
                for half, y in [("lower", 1), ("upper", 2)]:
                    put(
                        x,
                        y,
                        z,
                        "oak_door",
                        facing="south",
                        half=half,
                        hinge="left",
                        open=False,
                        powered=False,
                    )
                pos = point(x, 1, z)
            else:
                native_index = ["chests", "beds", "crafting table", "lamps"].index(
                    native
                )
                preferred = (2 + native_index * 3, ld - 3)
                positions = [preferred] + [
                    (a, b) for b in range(ld - 3, 4, -1) for a in range(2, lw - 2)
                ]
                native_offsets = [(0, 0), (0, 1)] if native == "beds" else [(0, 0)]
                placement = next(
                    (
                        (a, b)
                        for a, b in positions
                        if all(
                            1 <= a + dx < lw - 1
                            and 1 <= b + dz < ld - 1
                            and cells.get(world(a + dx, 1, b + dz), "air") == "air"
                            for dx, dz in native_offsets
                        )
                    ),
                    None,
                )
                if placement is None:
                    unsupported.append(f"{name}: no clear placement for {native}")
                    continue
                x, z = placement
                if native == "beds":
                    put(
                        x,
                        1,
                        z,
                        "white_bed",
                        facing="south",
                        part="foot",
                        occupied=False,
                    )
                    put(
                        x,
                        1,
                        z + 1,
                        "white_bed",
                        facing="south",
                        part="head",
                        occupied=False,
                    )
                else:
                    block = {
                        "chests": "chest",
                        "crafting table": "crafting_table",
                        "lamps": "glowstone",
                    }[native]
                    props = (
                        {"facing": "north", "type": "single", "waterlogged": False}
                        if native == "chests"
                        else {}
                    )
                    put(x, 1, z, block, **props)
                pos = point(x, 1, z)
            inventory.append(
                {
                    "type": native,
                    "capability": "native; live qualification required",
                    "position": pos,
                    "count": 1,
                }
            )
        if kind in {"building", "pavilion", "dock", "wreck", "tower"}:
            entry_x = 1 if kind == "tower" else lw // 2
            wx, _, wz = world(entry_x, 0, -1)
            px, pz = wx - terrain["origin"][0], wz - terrain["origin"][1]
            path_elevation = {
                (x, z): y for x, z, y in terrain["field"].get("paths", [])
            }
            approach = path_elevation.get((px, pz), terrain["field"]["height"][pz][px])
            if abs(approach - level) > 1:
                dependencies.append(
                    f"{name}: entrance needs a reviewed stair approach from elevation {approach} to {level}"
                )
            walks.insert(0, point(entry_x, approach - level + 1, -1))
            if kind == "tower":
                walks.append(point(lw // 2, h - 3, ld // 2))
            elif kind != "building":
                walks.append(point(lw // 2, 1, ld // 2))
                if kind == "dock":
                    walks.append(point(lw - 3, 1, ld // 2))
        for position, value in cells.items():
            if position in occupied and occupied[position] != value:
                dependencies.append(
                    f"{name}: overlaps another architecture component at {position}"
                )
            occupied[position] = value
        # Bottom-up solids, then dependent native elements; multipart pairs stay
        # adjacent in the desired sequence (the journal owns bounded write units).
        interactive = {"oak_door", "white_bed", "chest", "furnace", "torch"}
        ordered = sorted(
            cells.items(),
            key=lambda item: (
                item[1].split("[")[0] in interactive,
                item[0][1],
                item[0][2],
                item[0][0],
            ),
        )
        result = [
            {"position": dict(zip(("x", "y", "z"), p)), "after": v} for p, v in ordered
        ]
        if len(result) > 100000:
            raise ValueError(f"{name}: architecture stage exceeds 100,000 cells")
        parts.append(
            {
                "name": name,
                "kind": kind,
                "box": [x0, z0, w, d, level, h],
                "turn": turn,
                "material": material_name,
                "extensions": extensions,
                "rooms": rooms,
                "objects": inventory,
                "walks": walks,
                "cells": result,
                "digest": digest(result),
                "source": deepcopy(component.get("requirement_source", {})),
            }
        )
    # Junction markers belong to the actual route graph, rather than a decorative
    # cluster at the diagram's provisional annotation box.
    for component in junction_components:
        nodes = {}
        for route in terrain["routes"]:
            for end, index in (("from", 0), ("to", -1)):
                label = route[end]
                node = nodes.setdefault(
                    label, {"point": route["points"][index][:2], "links": set()}
                )
                node["links"].add(route["to" if end == "from" else "from"])
        choices = sorted(
            ((name, node) for name, node in nodes.items() if len(node["links"]) >= 2),
            key=lambda item: (-len(item[1]["links"]), item[0]),
        )
        count = component.get("constraints", {}).get("count", 1)
        paths = {(x, z): y for x, z, y in terrain["field"].get("paths", [])}
        accepted = []
        for label, node in choices:
            if len(accepted) >= count:
                break
            ax, az = node["point"]
            if any(abs(ax - p[0]) + abs(az - p[1]) < 12 for p in accepted):
                continue
            candidates = sorted(
                (
                    (x, z)
                    for x in range(max(2, ax - 12), min(terrain["extent"] - 4, ax + 13))
                    for z in range(max(2, az - 12), min(terrain["extent"] - 3, az + 13))
                ),
                key=lambda p: abs(p[0] - ax) + abs(p[1] - az),
            )
            found = None
            for x, z in candidates:
                level = terrain["field"]["height"][z][x + 1]
                if any(
                    (x + i, z) in paths
                    or terrain["field"].get(
                        "water",
                        [[False] * terrain.get("extent", 64)]
                        * terrain.get("extent", 64),
                    )[z][x + i]
                    for i in range(3)
                ):
                    continue
                nearby = [
                    (px, pz, y)
                    for (px, pz), y in paths.items()
                    if abs(px - (x + 1)) + abs(pz - z) <= 2 and abs(y - level) <= 1
                ]
                if not nearby:
                    continue
                local = assembly("signpost", materials)
                cells = [
                    {
                        "position": {
                            "x": terrain["origin"][0] + x + dx,
                            "y": sea + level + 1 + dy,
                            "z": terrain["origin"][1] + z + dz,
                        },
                        "after": state(palette, block),
                    }
                    for (dx, dy, dz), block in local.items()
                ]
                if any(
                    tuple(c["position"][k] for k in ("x", "y", "z")) in occupied
                    for c in cells
                ):
                    continue
                found = (x, z, level, cells, nearby[0])
                break
            if found is None:
                continue
            x, z, level, cells, approach = found
            accepted.append((ax, az))
            part_name = f"{component['name']} · {len(accepted)}"
            parts.append(
                {
                    "name": part_name,
                    "source_component": component["name"],
                    "kind": "decoration",
                    "box": [x, z, 3, 1, level, 3],
                    "turn": 0,
                    "material": material_name,
                    "extensions": [],
                    "rooms": [],
                    "objects": [
                        {
                            "type": "signpost",
                            "capability": CATALOG["signpost"][0],
                            "label": label + ": " + ", ".join(sorted(node["links"])),
                            "count": 1,
                            "position": cells[0]["position"],
                        }
                    ],
                    "walks": [
                        {
                            "x": terrain["origin"][0] + approach[0],
                            "y": sea + approach[2] + 1,
                            "z": terrain["origin"][1] + approach[1],
                        }
                    ],
                    "cells": cells,
                    "digest": digest(cells),
                    "source": deepcopy(component.get("requirement_source", {})),
                }
            )
            for c in cells:
                occupied[tuple(c["position"][k] for k in ("x", "y", "z"))] = c["after"]
        if len(accepted) != count:
            dependencies.append(
                f"{component['name']}: found {len(accepted)} of {count} distinct accessible route junctions"
            )
    if selected and not parts and not dependencies and not unsupported:
        raise ValueError("No supported selected architecture component")
    result = {
        "version": 1,
        "design_revision": design["revision"],
        "terrain_digest": terrain["digest"],
        "terrain_revision": terrain["design_revision"],
        "region": deepcopy(terrain["region"]),
        "components": parts,
        "unsupported": sorted(set(unsupported)),
        "dependencies": sorted(set(dependencies)),
        "max_seconds": 7200,
        "cells": sum(len(c["cells"]) for c in parts),
    }
    result["digest"] = digest(result)
    return result
