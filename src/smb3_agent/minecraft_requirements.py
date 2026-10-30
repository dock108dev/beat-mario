"""Provenance-backed design requirements and bounded model layout decisions.

Explicit user facts are application constraints, not facts a language model may
rewrite. Named prose clauses form an inspectable checklist; unknown prose remains
visible instead of being silently dropped.
"""

from copy import deepcopy
import hashlib
import re

from smb3_agent.minecraft_planning import schema

MAX_CALLS = 32
MAX_SECONDS = 1200
BATCH_SIZE = 3
WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
}
KINDS = [
    ("pavilion", r"\bpavilion\b|\bopen shelter\b"),
    ("platform", r"\bplatform\b"),
    ("bridge", r"\bbridge\b"),
    ("dock", r"\bdock\b"),
    ("wreck", r"\bwreck\b"),
    ("cave", r"\bcave\b"),
    ("tower", r"\btower\b|\bbeacon\b"),
    ("grove", r"\bgrove\b|\bwoodland\b|\borchard\b|\bforest patch\b"),
    ("water", r"\bwater\b|\briver\b|\bocean\b|\bbay\b|\bcove\b"),
    ("path", r"\bpath\b|\btrail\b"),
    ("building", r"\bbuilding\b|\bstation\b|\binn\b|\blodge\b|\bmill\b|\bgreenhouse\b"),
    ("decoration", r"\bdecorat(?:ion|ive)\b|\bassembl(?:y|ies)\b|\bobjects?\b"),
    (
        "terrain",
        r"\bterrain\b|\bclearing\b|\bterrace\b|\bridge\b|\bbeach\b|\blookout\b|\bslope\b|\bland\b|\bmarket\b",
    ),
]
DEFAULTS = {
    "pavilion": (8, 6, 4),
    "platform": (8, 6, 3),
    "building": (16, 12, 6),
    "bridge": (12, 3, 2),
    "dock": (20, 5, 2),
    "wreck": (24, 8, 5),
    "cave": (24, 10, 4),
    "tower": (9, 9, 18),
    "grove": (24, 20, 12),
    "water": (48, 12, 2),
    "path": (24, 3, 1),
    "terrain": (48, 32, 12),
    "decoration": (8, 8, 3),
}
BACKGROUND = {"water", "terrain", "grove", "path"}


def canonical(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def numbers(text):
    return re.sub(
        r"\b(" + "|".join(WORDS) + r")\b",
        lambda m: str(WORDS[m[1].lower()]),
        text,
        flags=re.I,
    )


def kind_of(name, body):
    # A type immediately following a label is more specific than objects within it.
    first = body.split(";")[0].split(".")[0]
    explicit = re.sub(r"^(?:(?:a|an|open)\s+)+", "", first.strip(), flags=re.I)
    for kind, pattern in KINDS:
        if re.match("(?:" + pattern + ")", explicit, re.I):
            return kind
    for text in (name, first):
        for kind, pattern in KINDS:
            if re.search(pattern, text, re.I):
                return kind
    return None


def extract(name, body, source, start, old=None):
    value = (
        deepcopy(old)
        if old
        else {
            "name": name,
            "rooms": [],
            "connections": [],
            "objects": [],
            "native": [],
            "constraints": {},
        }
    )
    value["name"] = name
    value["source"] = {
        "request": source["id"],
        "start": start,
        "end": start + len(body),
        "quote": body,
    }
    value.setdefault("field_sources", {})
    text = numbers(body).lower()
    constraints = value["constraints"]

    def put(key, val):
        constraints[key] = val
        value["field_sources"][key] = deepcopy(value["source"])

    kind = kind_of(name, body)
    if kind:
        put("kind", kind)
    dimensions = re.search(
        r"\b(\d+)\s*(?:by|x|×)\s*(\d+)(?:\s*(?:by|x|×)\s*(\d+))?", text
    )
    if dimensions:
        put("width", int(dimensions[1]))
        put("depth", int(dimensions[2]))
        if dimensions[3]:
            put("height", int(dimensions[3]))
    for key, pattern in [
        ("height", r"(?:height\s*:?\s*|)(\d+)\s*(?:blocks?\s+)?high\b"),
        ("height", r"\bheight\s*:?\s*(\d+)"),
        ("elevation", r"\belevation\s*:?\s*(-?\d+)"),
        ("width", r"\bwidth\s*:\s*(\d+)"),
        ("depth", r"\bdepth\s*:\s*(\d+)"),
    ]:
        match = re.search(pattern, text)
        if match:
            put(key, int(match[1]))
    diameter = re.search(r"(\d+)[ -](?:block[ -])?diameter", text)
    if diameter:
        put("width", int(diameter[1]))
        put("depth", int(diameter[1]))
    if re.search(r"\brotat(?:e|ed|ion)\b", text):
        degrees = re.search(r"(90|180|270)\s*(?:degrees?|°)", text)
        put("turn", int(degrees[1]) // 90 if degrees else 1)
    elif not old:
        put("turn", 0)
    storeys = re.search(r"(\d+)[ -](?:storey|story)", text)
    if storeys:
        put("storeys", int(storeys[1]))
        if "height" not in constraints:
            put("height", max(4, int(storeys[1]) * 5))
    for key, pattern in [
        ("rooms", r"\brooms?\s*:\s*([^.;]+)"),
        ("objects", r"\bobjects?\s*:\s*([^.;]+)"),
        ("native", r"\bnative\s*:\s*([^.;]+)"),
        ("connections", r"\bconnects? to\s+([^.;]+)"),
    ]:
        match = re.search(pattern, body, re.I)
        if match:
            value[key] = [
                x.strip(" .")
                for x in re.split(r",|\s+and\s+|\s*/\s*", match[1])
                if x.strip(" .")
            ]
            value["field_sources"][key] = deepcopy(value["source"])
    count = re.search(
        r"\b(\d+)\s+(?:distinct\s+|separated\s+|signposted\s+|exposed\s+)?(?:awnings|stalls|patches|terraces|junctions|ribs)\b",
        text,
    )
    if count:
        put("count", int(count[1]))
    border = re.search(r"\bborder\s+(?:at least\s+)?(\d+)", text)
    if border:
        put("border", int(border[1]))
    for zone in ("north", "south", "east", "west", "center"):
        if re.search(r"\b" + zone + r"\b", text):
            put("zone", zone)
            break
    if "larger inside" in text and not dimensions and old:
        for key in ("width", "depth"):
            put(
                key + "_min",
                old["constraints"].get(key, DEFAULTS.get(kind, (16, 12, 6))[0]) + 2,
            )
            constraints.pop(key, None)
    value["measurements"] = [
        {
            "quote": m[0],
            "values": [int(x) for x in re.findall(r"\d+", m[0])],
            "source": deepcopy(value["source"]),
        }
        for m in re.finditer(
            r"\d+(?:\s*(?:by|x|×|to|–|-)\s*\d+)*(?:\s+(?:blocks?|rooms?|patches|stalls|ribs|junctions))?",
            body,
            re.I,
        )
    ]
    value["details"] = (
        body if not old else old.get("details", "") + "\nRevision: " + body
    )
    value["issues"] = []
    footprints = list(re.finditer(r"\b\d+\s*(?:by|x|×)\s*\d+", text))
    for extra in footprints[1:]:
        prefix = text[max(0, extra.start() - 45) : extra.start()]
        if (
            not re.search(r"chamber|room|passage|interior|awning|stall", prefix)
            and extra[0] != footprints[0][0]
        ):
            value["issues"].append(
                "Conflicting footprint dimensions; specify one component footprint"
            )

    if not constraints.get("kind"):
        value["issues"].append("Choose a supported component shape")
    if re.search(
        r"(?<!no )(?<!not )\b(?:working|functional)\s+(?:aircraft|vehicle|economy|mill mechanism|radio|electrical network)\b",
        text,
    ):
        value["issues"].append(
            "Requested functional mechanism is unsupported; choose a decorative interpretation"
        )
    return value


def parse_request(text, current):
    source = {"id": hashlib.sha256(text.encode()).hexdigest()[:20], "text": text}
    previous = {r["name"]: deepcopy(r) for r in (current or {}).get("requirements", [])}
    requirements = deepcopy(previous)
    unknown = list((current or {}).get("planning", {}).get("issues", []))
    if re.fullmatch(r"ignore unrecognized notes[.! ]*", text, re.I):
        unknown = []
    changed = []
    extent = (current or {}).get("extent")
    missing_extent = "Specify the project extent: 192 by 192 or 256 by 256"
    missing_places = "Name each required place on its own line, for example Camp: open pavilion 8 by 6, 4 blocks high."
    # A placeholder size in an incomplete brief is not an accepted project extent.
    if missing_extent in unknown:
        extent = None
    match = re.search(r"\b(192|256)\s*(?:by|x|×)\s*\1\b", text, re.I)
    if match:
        if extent is None:
            unknown = [issue for issue in unknown if issue not in
                       {missing_extent, "Changing the project extent needs a new project"}]
        if extent and extent != int(match[1]):
            unknown.append("Changing the project extent needs a new project")
        else:
            extent = int(match[1])
    if not extent:
        unknown.append("Specify the project extent: 192 by 192 or 256 by 256")
    palette = (current or {}).get("palette", "warm")
    if re.search(r"less industrial|natural|spruce", text, re.I):
        palette = "natural"
    elif re.search(r"industrial", text, re.I):
        palette = "industrial"
    elif re.search(r"coastal|brighter", text, re.I):
        palette = "coastal"
    elif re.search(r"warm|pale fabric", text, re.I):
        palette = "warm"
    title = (current or {}).get("title") or re.split(
        r"[,.;\n]", re.sub(r"^(?:plan|design|build)\s+", "", text, flags=re.I)
    )[0][:60]
    clauses = []
    for m in re.finditer(r"[^\n;]+", text):
        segment = m[0].strip()
        if not segment:
            continue
        label = re.match(r"([\w][\w '\-]{0,47}):\s*(.+)", segment)
        if label:
            name, body = label[1].strip(), label[2].strip()
            clauses.append((name, body, text.index(body, m.start())))
            continue
        # Ordinary targeted prose uses the existing name, never a fuzzy replacement.
        named = [
            name
            for name in previous
            if re.search(r"\b" + re.escape(name) + r"\b", segment, re.I)
        ]
        if named and re.match(
            r"(?:make|move|rotate|change|resize|revise)\b", segment, re.I
        ):
            name = min(
                named,
                key=lambda n: (
                    re.search(r"\b" + re.escape(n) + r"\b", segment, re.I).start(),
                    -len(n),
                ),
            )
            clauses.append((name, segment, text.index(segment, m.start())))
            continue
        if re.match(r"add\s+", segment, re.I):
            body = re.sub(r"^add\s+", "", segment, flags=re.I)
            parts = re.split(r"\s+and\s+(?=(?:a|an)\s+)", body, flags=re.I)
            for part in parts:
                part = re.split(r"[.;]", part)[0].strip()
                name = re.sub(r"^(?:a|an)\s+", "", part, flags=re.I)
                name = re.sub(r"\b(?:rotated|small|open)\s+", "", name, flags=re.I)
                name = re.split(
                    r",|\b(?:size|with|that|measuring)\b|\s+(?=\d+\s*(?:by|x|×))",
                    name,
                    flags=re.I,
                )[0].strip()
                if len(name) > 48 or not kind_of(name, part):
                    unknown.append(part)
                    continue
                name = name[0].upper() + name[1:]
                clauses.append((name, part, text.index(part)))
            continue
        if re.match(
            r"(?:plan|design|build|preserve|keep|retain|use|continue|ignore unrecognized notes)\b",
            segment,
            re.I,
        ) or re.search(r"palette|less industrial|warm timber", segment, re.I):
            # Header/style statements are retained separately, not interpreted as components.
            if (
                not match
                and not current
                and re.match(r"(?:plan|design|build)\b", segment, re.I)
            ):
                unknown.append(segment)
            continue
        unknown.append(segment)
    for name, body, start in clauses:
        existing = next(
            (n for n in requirements if canonical(n) == canonical(name)), name
        )
        old = requirements.get(existing)
        r = extract(existing, body, source, start, old)
        if existing not in changed:
            changed.append(existing)
        requirements[existing] = r
    if clauses:
        unknown = [issue for issue in unknown if issue != missing_places]
    if not clauses and not current:
        unknown.append(
            "Name each required place on its own line, for example Camp: open pavilion 8 by 6, 4 blocks high."
        )
    names = {canonical(n): n for n in requirements}
    for name, r in requirements.items():
        r["issues"] = [
            issue
            for issue in r["issues"]
            if not issue.startswith("Unresolved connection:")
        ]
        for field in ("connections",):
            links = []
            for link in r[field]:
                actual = names.get(canonical(link))
                if not actual:
                    r["issues"].append("Unresolved connection: " + link)
                    links.append(link)
                else:
                    links.append(actual)
            r[field] = links
        if name in changed and r["constraints"].get("kind") == "bridge" and not r["connections"]:
            waterways = [n for n, other in requirements.items() if other["constraints"].get("kind") == "water" and max(other["constraints"].get("width", 0), other["constraints"].get("depth", 0)) >= 2 * max(1, min(other["constraints"].get("width", 0), other["constraints"].get("depth", 0)))]
            if len(waterways) == 1:
                r["connections"] = waterways
                r["anchor"] = waterways[0]
            else:
                r["issues"].append("Name the waterway this bridge should cross")
        text_lower = r["source"]["quote"].lower()
        if name in changed and ("nearer" in text_lower or "riverside" in text_lower):
            anchors = [
                n
                for n in requirements
                if n != name
                and (
                    n.lower() in text_lower
                    or (
                        "riverside" in text_lower
                        and requirements[n]["constraints"].get("kind") == "water"
                        and "river" in n.lower()
                    )
                )
            ]
            if anchors:
                r["connections"] = list(dict.fromkeys(r["connections"] + [anchors[0]]))
                r["relocate"] = True
                r["anchor"] = anchors[0]
            else:
                r["issues"].append("Name the place this should move closer to")
    if len(requirements) > 40:
        unknown.append("More than 40 named components; split the brief before planning")
    return {
        "source": source,
        "requirements": list(requirements.values()),
        "changed": changed,
        "issues": unknown,
        "extent": extent or 256,
        "title": title,
        "palette": palette,
    }


def proposal_schema(requirements):
    properties = {}
    for i, r in enumerate(requirements):
        c = r["constraints"]
        default = DEFAULTS[c["kind"]]

        def number(key, default_value, maximum):
            if key in c:
                return {"type": "integer", "enum": [c[key]]}
            minimum = c.get(key + "_min", max(1, default_value // 2))
            return {
                "type": "integer",
                "minimum": minimum,
                "maximum": min(maximum, max(minimum, default_value * 2)),
            }

        properties[str(i)] = schema(
            {
                "width": number("width", default[0], 256),
                "depth": number("depth", default[1], 256),
                "height": number("height", default[2], 48),
                "zone": {
                    "type": "string",
                    "enum": [c["zone"]]
                    if "zone" in c
                    else ["north", "south", "east", "west", "center"],
                },
            }
        )
    return schema(properties)


def reconcile(requirements, proposal):
    from smb3_agent.inference_contract import validate_object

    validate_object(proposal, proposal_schema(requirements))
    components = []
    for i, r in enumerate(requirements):
        p = proposal[str(i)]
        c = r["constraints"]
        if c.get("storeys") and p["height"] < c["storeys"] * 4:
            raise ValueError("Storeys need at least four blocks each")
        components.append(
            {
                "name": r["name"],
                "kind": c["kind"],
                "size": [p["width"], p["depth"], p["height"]],
                "zone": p["zone"],
                "level": "shore",
                "turn": c.get("turn", 0),
                "link": r.get("anchor")
                or (r["connections"][0] if r["connections"] else ""),
                "detail": "Source requirements retained; inspect the checklist.",
            }
        )
    return components


def checklist(design):
    by_name = {c["name"]: c for c in design["components"]}
    rows = []
    for r in design.get("requirements", []):
        component = by_name.get(r["name"])
        issues = list(r["issues"])
        facts = r["constraints"]
        if not component:
            issues.append("Not planned yet")
        else:
            for key, index in (("width", 0), ("depth", 1), ("height", 2)):
                if key in facts and component["size"][index] != facts[key]:
                    issues.append(key + " differs from brief")
                if (
                    key + "_min" in facts
                    and component["size"][index] < facts[key + "_min"]
                ):
                    issues.append(key + " is too small")
            for key in ("kind", "turn"):
                if key in facts and component[key] != facts[key]:
                    issues.append(key + " differs from brief")
            for field in ("rooms", "connections", "objects", "native"):
                if component.get(field, []) != r[field]:
                    issues.append(field + " differ from brief")
            if "elevation" in facts and component["box"][4] != facts["elevation"]:
                issues.append("elevation differs from brief")
            if component.get("requirement_source") != r["source"]:
                issues.append("Needs current requirement review")
        rows.append(
            {
                "name": r["name"],
                "status": "pending" if issues else "matched",
                "issues": issues,
                "rooms": r["rooms"],
                "connections": r["connections"],
                "objects": r["objects"],
                "native": r["native"],
                "constraints": facts,
                "source": r["source"],
                "details": r["details"],
            }
        )
    return rows
