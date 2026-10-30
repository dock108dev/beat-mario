"""Pure, generic terrain compilation from reviewed requirements; no world I/O."""

from collections import deque
from copy import deepcopy
import hashlib
import heapq
import json
import re

TILE = 64
MAX_CELLS = 2_000_000
MAX_SECONDS = 7200
SEA = -47
FLOOR = -60


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def compile_terrain(design, origin):
    if design.get("planning", {}).get("state") != "ready":
        raise ValueError("Resolve the design requirements before reviewing terrain")
    n = design["extent"]
    if n not in (192, 256):
        raise ValueError("Unsupported terrain extent")
    components = deepcopy(design["components"])
    if not components:
        raise ValueError("No terrain requirements")
    rows = {r["name"]: r for r in design["requirements"]}
    by_name = {c["name"]: c for c in components}
    ocean = next(
        (
            c
            for c in components
            if c["kind"] == "water" and c.get("constraints", {}).get("border")
        ),
        None,
    )
    land = next(
        (
            c
            for c in components
            if c["kind"] == "terrain"
            and c["size"][0] >= n // 2
            and c["size"][1] >= n // 2
        ),
        None,
    )
    height = [[0 for _ in range(n)] for _ in range(n)]
    water = [[False for _ in range(n)] for _ in range(n)]
    sand = [[False for _ in range(n)] for _ in range(n)]
    reserve = {}
    caves = []
    objects = {}

    def box(c):
        x, z, w, d, level, h = c["box"]
        return x, z, w, d, level, h

    def center(c):
        x, z, w, d, *_ = box(c)
        return min(n - 2, max(1, x + w // 2)), min(n - 2, max(1, z + d // 2))

    if ocean:
        border = max(16, ocean["constraints"]["border"])
        lw, ld = land["size"][:2] if land else [n - 2 * border, n - 2 * border]
        rx, rz = (
            min(lw / 2 - 1, n / 2 - border - 1),
            min(ld / 2 - 1, n / 2 - border - 1),
        )
        for z in range(n):
            for x in range(n):
                water[z][x] = ((x - (n - 1) / 2) / rx) ** 2 + (
                    (z - (n - 1) / 2) / rz
                ) ** 2 > 1
    # Explicit water footprints cut channels/bays; an enclosing ocean is a boundary.
    for c in components:
        if c["kind"] != "water" or c is ocean:
            continue
        x0, z0, w, d, level, h = box(c)
        for z in range(max(1, z0), min(n - 1, z0 + d)):
            for x in range(max(1, x0), min(n - 1, x0 + w)):
                water[z][x] = True
                height[z][x] = max(-12, level)
    for z in range(n):
        for x in range(n):
            if water[z][x] and height[z][x] == 0:
                height[z][x] = -4
    # Hills are bounded 1:1 pyramidal slopes. Broad base land is not a hill.
    for c in components:
        if c["kind"] != "terrain" or c is land or c["size"][2] < 8:
            continue
        x0, z0, w, d, level, h = box(c)
        cx, cz = center(c)
        for z in range(max(1, z0), min(n - 1, z0 + d)):
            for x in range(max(1, x0), min(n - 1, x0 + w)):
                if not water[z][x]:
                    peak = min(h, max(0, min(w, d) // 2 - 1))
                    height[z][x] = max(
                        height[z][x],
                        min(
                            peak,
                            max(0, min(x - x0, z - z0, x0 + w - 1 - x, z0 + d - 1 - z)),
                        ),
                    )
        # A sufficiently wide footprint must retain its requested peak height.
        if h > min(w, d) // 2 - 1:
            # Broader smooth ramps may extend beyond a schematic hill footprint.
            for z in range(1, n - 1):
                for x in range(1, n - 1):
                    if not water[z][x]:
                        height[z][x] = max(
                            height[z][x], max(0, h - abs(x - cx) - abs(z - cz))
                        )
    # Repeated retaining terraces have level treads and a continuous side ramp.
    for c in components:
        count = c.get("constraints", {}).get("count", 0)
        if (
            c["kind"] != "terrain"
            or count < 2
            or "terrace" not in rows[c["name"]]["details"].lower()
        ):
            continue
        x0, z0, w, d, level, h = box(c)
        for z in range(max(1, z0), min(n - 1, z0 + d)):
            for x in range(max(1, x0), min(n - 1, x0 + w)):
                if not water[z][x]:
                    step = min(count, 1 + (z - z0) * count // d)
                    top = round(h * step / count)
                    ramp = min(h, max(0, z - z0)) if x < x0 + 4 else top
                    height[z][x] = level + ramp
    # Reserve future structures and clearings, with graded approaches rather than cliffs.
    for c in components:
        if c["kind"] not in {
            "building",
            "platform",
            "decoration",
            "pavilion",
            "tower",
            "dock",
            "bridge",
            "wreck",
            "cave",
        } and not (c["kind"] == "terrain" and c["size"][2] < 8):
            continue
        x0, z0, w, d, level, h = box(c)
        if c["kind"] == "terrain" and level > 0:
            # A raised lookout cannot share a lower tower's footprint. Resolve
            # schematic overlap in the reviewed terrain layout, never in secret at write time.
            def fits(x, z):
                if water[min(n - 1, z + d // 2)][min(n - 1, x + w // 2)]:
                    return False
                for other in reserve.values():
                    ax, az, aw, ad = other["box"]
                    gap = max(ax - (x + w - 1), x - (ax + aw - 1), 0) + max(
                        az - (z + d - 1), z - (az + ad - 1), 0
                    )
                    if gap < abs(level - other["level"]):
                        return False
                return True

            choices = [
                (x, z)
                for z in range(16, n - d - 15, 4)
                for x in range(16, n - w - 15, 4)
                if fits(x, z)
            ]
            if not choices:
                raise ValueError(
                    "Raised lookout conflicts with required entrances; revise layout"
                )
            x0, z0 = min(choices, key=lambda p: abs(p[0] - x0) + abs(p[1] - z0))
            c["box"] = [x0, z0, w, d, level, h]
        if c["kind"] == "cave":
            x0, z0 = center(c)
            w = d = 3
        level = max(1 if c["kind"] in {"dock", "bridge"} else 0, level)
        reserve[c["name"]] = {
            "box": [x0, z0, w, d],
            "level": level,
            "entrance": list(center(c)),
        }
        for z in range(1, n - 1):
            for x in range(1, n - 1):
                dist = max(x0 - x, 0, x - (x0 + w - 1)) + max(
                    z0 - z, 0, z - (z0 + d - 1)
                )
                if dist < 48 and not water[z][x]:
                    height[z][x] = min(level + dist, max(level - dist, height[z][x]))
    # Shore-distance gives a continuous six-block beach along the land edge.
    distance = [[999 for _ in range(n)] for _ in range(n)]
    queue = deque()
    for z in range(n):
        for x in range(n):
            if water[z][x]:
                distance[z][x] = 0
                queue.append((x, z))
    while queue:
        x, z = queue.popleft()
        for xx, zz in ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)):
            if 0 <= xx < n and 0 <= zz < n and distance[zz][xx] > distance[z][x] + 1:
                distance[zz][xx] = distance[z][x] + 1
                queue.append((xx, zz))
    for z in range(n):
        for x in range(n):
            sand[z][x] = bool(ocean and not water[z][x] and distance[z][x] <= 6)
    peaks = []
    for c in components:
        if (
            c["kind"] != "terrain"
            or c is land
            or c["size"][2] < 8
            or c.get("constraints", {}).get("count", 0) > 1
        ):
            continue
        x0, z0, w, d, level, h = box(c)
        cx, cz = center(c)

        def reserved(x, z):
            return any(
                a["box"][0] <= x < a["box"][0] + a["box"][2]
                and a["box"][1] <= z < a["box"][1] + a["box"][3]
                for a in reserve.values()
            )

        def fits_peak(x, z):
            if water[z][x] or distance[z][x] < h:
                return False
            for a in reserve.values():
                ax, az, aw, ad = a["box"]
                dist = max(ax - x, 0, x - (ax + aw - 1)) + max(
                    az - z, 0, z - (az + ad - 1)
                )
                if h > a["level"] + dist:
                    return False
            return True

        choices = [
            (x, z) for z in range(1, n - 1) for x in range(1, n - 1) if fits_peak(x, z)
        ]
        if not choices:
            raise ValueError(
                "Hill height conflicts with water and reserved entrances; revise layout"
            )
        px, pz = min(choices, key=lambda p: abs(p[0] - cx) + abs(p[1] - cz))
        for z in range(1, n - 1):
            for x in range(1, n - 1):
                if not water[z][x]:
                    value = max(height[z][x], h - abs(x - px) - abs(z - pz))
                    value = min(value, distance[z][x])
                    for a in reserve.values():
                        ax, az, aw, ad = a["box"]
                        dist = max(ax - x, 0, x - (ax + aw - 1)) + max(
                            az - z, 0, z - (az + ad - 1)
                        )
                        value = min(value, a["level"] + dist)
                    height[z][x] = value
        peaks.append({"name": c["name"], "position": [px, pz], "height": h})
    # Cave passages/chambers are explicit carved volumes with a dry, connected entrance.
    for c in components:
        if c["kind"] != "cave":
            continue
        x, z = center(c)
        description = rows[c["name"]]["details"]
        chamber = re.search(r"chamber\s+(\d+)\s+by\s+(\d+)", description, re.I)
        length_match = re.search(r"passage\s+(\d+)", description, re.I)
        cw, cd = map(int, chamber.groups()) if chamber else (10, 8)
        length = int(length_match[1]) if length_match else c["size"][0]
        if max(cw, cd, length) > 48:
            raise ValueError("Cave exceeds bounded passage/chamber limits")
        y = max(0, c["box"][4])
        if z + length + cd >= n - 1:
            raise ValueError(
                "Cave entrance needs space for the requested passage and chamber"
            )
        cavities = []
        for zz in range(z, z + length + cd):
            half = cw // 2 if zz >= z + length else 1
            for xx in range(x - half, x - half + (cw if zz >= z + length else 3)):
                if not 1 <= xx < n - 1 or water[zz][xx]:
                    raise ValueError(
                        "Cave conflicts with water or project bounds; revise its location"
                    )
                height[zz][xx] = max(height[zz][xx], y + 4)
                cavities.append([xx, zz])
        for xx, zz in cavities:
            for ax, az in ((xx - 1, zz), (xx + 1, zz), (xx, zz + 1)):
                if 1 <= ax < n - 1 and 1 <= az < n - 1 and not water[az][ax]:
                    height[az][ax] = max(height[az][ax], y + 4)
        caves.append(
            {
                "name": c["name"],
                "floor": y,
                "headroom": 2,
                "entrance_headroom": 3,
                "passage": length,
                "chamber": [cw, cd],
                "cells": cavities,
                "entrance": [x, z],
            }
        )
    # Paths are routed on the graded surface. Water crossings become explicit raised boardwalks.
    walk = [
        [max(1, height[z][x]) if water[z][x] else height[z][x] for x in range(n)]
        for z in range(n)
    ]
    # Cave mouths are lower than their roofs. Only the open entrance row belongs
    # to surface navigation; tunnel floors are carved independently underneath.
    for cave in caves:
        x, z = cave["entrance"]
        for xx in range(x - 1, x + 2):
            walk[z][xx] = cave["floor"]
    peak_positions = {p["name"]: tuple(p["position"]) for p in peaks}

    def destination(c):
        return peak_positions.get(c["name"], center(c))

    routes = []
    path_cells = {}

    def route(start, end, width, endpoints):
        blocked = [
            c["box"]
            for c in components
            if c["name"] not in endpoints
            and c["kind"] in {"building", "pavilion", "tower", "wreck"}
        ]
        # Overlapping draft sites are still terrain previews; architecture review
        # requires separating them before construction. Do not trap an endpoint
        # inside another unbuilt reservation while reviewing that draft.
        margin = width // 2
        blocked = [
            box
            for box in blocked
            if not any(
                box[0] - margin <= p[0] < box[0] + box[2] + margin
                and box[1] - margin <= p[1] < box[1] + box[3] + margin
                for p in (start, end)
            )
        ]
        heap = [(0, start)]
        cost = {start: 0}
        previous = {}
        while heap:
            score, p = heapq.heappop(heap)
            if score != cost[p]:
                continue
            if p == end:
                break
            x, z = p
            for q in ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)):
                xx, zz = q
                if not (1 <= xx < n - 1 and 1 <= zz < n - 1):
                    continue
                margin = width // 2
                if any(
                    a - margin <= xx < a + w + margin
                    and b - margin <= zz < b + d + margin
                    for a, b, w, d, *_ in blocked
                ):
                    continue
                if abs(walk[zz][xx] - walk[z][x]) > 1:
                    continue
                value = score + 1 + (8 if water[zz][xx] else 0)
                if value < cost.get(q, 10**9):
                    cost[q] = value
                    previous[q] = p
                    heapq.heappush(heap, (value, q))
        if end not in cost:
            raise ValueError(
                f"No graded route between requested destinations {start} -> {end}"
            )
        line = [end]
        while line[-1] != start:
            line.append(previous[line[-1]])
        line.reverse()
        for i, (x, z) in enumerate(line):
            along_x = i + 1 < len(line) and line[i + 1][0] != x
            for offset in range(-(width // 2), width - width // 2):
                xx, zz = (x, z + offset) if along_x else (x + offset, z)
                if 1 <= xx < n - 1 and 1 <= zz < n - 1:
                    # Intersecting widened routes share the same surface height.
                    # Copying the centre height can overwrite another route's
                    # graded centreline with a two-block step at a junction.
                    path_cells[xx, zz] = walk[zz][xx]
        return line

    links = set()
    for c in components:
        names = c.get("connections", [])
        if c["kind"] == "path" and len(names) > 1:
            pairs = list(zip(names, names[1:]))
            width = min(c["size"][:2])
        else:
            pairs = [
                (c["name"], name)
                for name in names
                if by_name.get(name, {}).get("kind") not in {"water", "path", "grove"}
                and c["kind"] not in {"water", "grove"}
            ]
            width = min(c["size"][:2]) if c["kind"] == "bridge" else 2
        for a, b in pairs:
            if a not in by_name or b not in by_name or a == b:
                continue
            key = tuple(sorted((a, b)))
            if key in links:
                existing = next(
                    r for r in routes if tuple(sorted((r["from"], r["to"]))) == key
                )
                if existing["width"] >= min(5, max(2, width)):
                    continue
                routes.remove(existing)
            links.add(key)
            line = route(
                destination(by_name[a]),
                destination(by_name[b]),
                min(5, max(2, width)),
                {a, b},
            )
            routes.append(
                {
                    "from": a,
                    "to": b,
                    "width": min(5, max(2, width)),
                    "points": [list(p) for p in line],
                }
            )
    # Crossings retain their full reviewed width, even when approach routes
    # meet in the middle or leave different sides of the reserved footprint.
    for c in components:
        if c["kind"] == "bridge":
            x0, z0, w, d, level, _ = box(c)
            for z in range(z0, z0 + d):
                for x in range(x0, x0 + w):
                    path_cells[x, z] = max(1, level)
    # Preserve requested patch counts; relocate groups inside the grove rather
    # than dropping trees that happen to land in a bay or structure reservation.
    groups = []
    for c in components:
        if c["kind"] != "grove":
            continue
        x0, z0, w, d, *_ = box(c)
        count = c.get("constraints", {}).get("count", 1)
        centers = []

        def tree_site(x, z):
            return (
                3 <= x < n - 3
                and 3 <= z < n - 3
                and not water[z][x]
                and all(
                    (x + dx, z + dz) not in path_cells
                    for dx in range(-2, 3)
                    for dz in range(-2, 3)
                )
                and not any(
                    a["box"][0] - 3 <= x < a["box"][0] + a["box"][2] + 3
                    and a["box"][1] - 3 <= z < a["box"][1] + a["box"][3] + 3
                    for a in reserve.values()
                )
            )

        offsets = ((0, 0), (-4, 3), (4, -3))
        for group in range(count):
            gx = x0 + (group + 1) * w // (count + 1)
            gz = z0 + d // 2
            candidates = [
                (x, z)
                for z in range(max(4, z0), min(n - 4, z0 + d))
                for x in range(max(4, x0), min(n - 4, x0 + w))
                if all(tree_site(x + dx, z + dz) for dx, dz in offsets)
                and all(abs(x - a) + abs(z - b) >= 12 for a, b in centers)
            ]
            if not candidates:
                raise ValueError(
                    "Requested woodland patches conflict with water or reserved entrances"
                )
            gx, gz = min(candidates, key=lambda p: abs(p[0] - gx) + abs(p[1] - gz))
            centers.append((gx, gz))
            groups.append({"name": c["name"], "group": group + 1, "center": [gx, gz]})
            for dx, dz in offsets:
                x, z = gx + dx, gz + dz
                objects[f"{x},{z}"] = {
                    "ground": height[z][x],
                    "height": 4,
                    "kind": "tree",
                }
    # Boundary rim contains water within the reviewed extent; the outer 32 blocks are never writable.
    for i in range(n):
        for x, z in ((i, 0), (i, n - 1), (0, i), (n - 1, i)):
            water[z][x] = False
            height[z][x] = max(1, height[z][x])
    field = {
        "height": height,
        "water": water,
        "sand": sand,
        "paths": [[x, z, y] for (x, z), y in sorted(path_cells.items())],
        "caves": caves,
        "trees": objects,
    }
    region = {
        "bounds": {
            "min": {"x": origin[0], "y": FLOOR, "z": origin[1]},
            "max": {"x": origin[0] + n - 1, "y": SEA + 48, "z": origin[1] + n - 1},
        },
        "protected": [],
        "observation_bounds": {
            "min": {"x": origin[0] - 32, "y": FLOOR, "z": origin[1] - 32},
            "max": {"x": origin[0] + n + 31, "y": SEA + 48, "z": origin[1] + n + 31},
        },
    }
    result = {
        "version": 2,
        "tile_size": TILE,
        "woodland_groups": groups,
        "design_revision": design["revision"],
        "extent": n,
        "origin": origin,
        "sea_level": SEA,
        "floor": FLOOR,
        "region": region,
        "buffer": 32,
        "field": field,
        "routes": routes,
        "reservations": reserve,
        "peaks": peaks,
        "source_digest": digest(design["requirements"]),
        "max_seconds": MAX_SECONDS,
        "max_cells": MAX_CELLS,
    }
    result["digest"] = digest(result)
    return result


def foliage_cells(manifest, palette):
    """Stable native leaves, ordered by distance from already placed trunks."""
    trees = manifest["field"].get("trees", {})
    logs = set()
    canopy = set()
    ox, oz = manifest["origin"]
    for key, tree in trees.items():
        x, z = map(int, key.split(","))
        base = SEA + tree["ground"]
        for y in range(base + 1, base + tree["height"] + 1):
            logs.add((x, y, z))
        for dz in range(-2, 3):
            for dx in range(-2, 3):
                for dy in (3, 4, 5):
                    if abs(dx) + abs(dz) <= (2 if dy == 5 else 3):
                        canopy.add((x + dx, base + dy, z + dz))
    result = []
    for x, y, z in sorted(canopy - logs):
        distance = min(abs(x - a) + abs(y - b) + abs(z - c) for a, b, c in logs)
        if not 1 <= distance <= 6:
            raise ValueError("Canopy has no bounded native support")
        state = (
            palette["oak_leaves"]
            .replace("distance=7", f"distance={distance}")
            .replace("persistent=false", "persistent=true")
        )
        result.append(
            {
                "position": {"x": ox + x, "y": y, "z": oz + z},
                "after": state,
                "distance": distance,
            }
        )
    return sorted(result, key=lambda c: c["distance"])


def foliage_cleanup(previous, current, palette):
    """Remove only connected foliage affected by changed trunks, outside-in."""
    old = previous["field"].get("trees", {})
    new = current["field"].get("trees", {})
    changed = [key for key, value in old.items() if new.get(key) != value]
    if not changed:
        return []
    ox, oz = previous["origin"]
    leaves = foliage_cells(previous, palette)
    cells = {tuple(c["position"][k] for k in ("x", "y", "z")): c for c in leaves}
    queue = []
    for key in changed:
        x, z = map(int, key.split(","))
        base = SEA + old[key]["ground"]
        for y in range(base + 1, base + old[key]["height"] + 1):
            for dx, dy, dz in (
                (1, 0, 0),
                (-1, 0, 0),
                (0, 1, 0),
                (0, -1, 0),
                (0, 0, 1),
                (0, 0, -1),
            ):
                queue.append((ox + x + dx, y + dy, oz + z + dz))
    affected = set()
    while queue:
        p = queue.pop()
        if p in affected or p not in cells:
            continue
        affected.add(p)
        x, y, z = p
        queue.extend(
            (x + dx, y + dy, z + dz)
            for dx, dy, dz in (
                (1, 0, 0),
                (-1, 0, 0),
                (0, 1, 0),
                (0, -1, 0),
                (0, 0, 1),
                (0, 0, -1),
            )
        )
    return [
        {"position": cells[p]["position"], "after": "air"}
        for p in sorted(affected, key=lambda p: -cells[p]["distance"])
    ]


def tile_cells(manifest, tx, tz, palette, *, fluid=False, leaves=0):
    n = manifest["extent"]
    ox, oz = manifest["origin"]
    f = manifest["field"]
    paths = {(x, z): y for x, z, y in f["paths"]}
    caves = {
        (x, z): (
            c["floor"],
            c.get("entrance_headroom", c["headroom"])
            if z < c["entrance"][1] + 2
            else c["headroom"],
        )
        for c in f["caves"]
        for x, z in c["cells"]
    }
    cells = {}
    tile = manifest.get("tile_size", 32)
    if leaves:
        return [
            {k: v for k, v in c.items() if k != "distance"}
            for c in foliage_cells(manifest, palette)
            if c["distance"] == leaves
            and ox + tx <= c["position"]["x"] < ox + tx + tile
            and oz + tz <= c["position"]["z"] < oz + tz + tile
        ]

    def put(x, y, z, name):
        if y < FLOOR or y > SEA + 48:
            raise ValueError("Terrain exceeds vertical bounds")
        cells[x, y, z] = palette[name]

    for z in range(tz, min(n, tz + tile)):
        for x in range(tx, min(n, tx + tile)):
            h = f["height"][z][x]
            wet = f["water"][z][x]
            if fluid:
                if wet:
                    for y in range(SEA + h + 1, SEA + 1):
                        put(x, y, z, "water")
                continue
            for y in range(FLOOR, SEA + h + 1):
                put(
                    x,
                    y,
                    z,
                    "sand"
                    if f["sand"][z][x] and y >= SEA + h - 1
                    else "grass_block"
                    if y == SEA + h and not wet
                    else "stone",
                )
            if wet:
                for y in range(SEA + h + 1, SEA + 1):
                    put(x, y, z, "glass")
            if (x, z) in paths:
                py = SEA + paths[x, z]
                for y in range(SEA + h + 1, py):
                    put(x, y, z, "stone")
                put(x, py, z, "oak_planks" if wet else "stone_bricks")
                for y in range(py + 1, py + 3):
                    put(x, y, z, "air")
            if (x, z) in caves:
                floor, clear = caves[x, z]
                put(x, SEA + floor, z, "stone_bricks")
                for y in range(SEA + floor + 1, SEA + floor + clear + 1):
                    put(x, y, z, "air")
            tree = f["trees"].get(f"{x},{z}")
            if tree:
                for y in range(
                    SEA + tree["ground"] + 1, SEA + tree["ground"] + tree["height"] + 1
                ):
                    put(x, y, z, "oak_log")
    return [
        {"position": {"x": ox + x, "y": y, "z": oz + z}, "after": state}
        for (x, y, z), state in sorted(
            cells.items(), key=lambda p: (p[0][1], p[0][2], p[0][0])
        )
    ]
