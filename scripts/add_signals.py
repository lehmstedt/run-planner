"""Add traffic lights and stop signs to map-data.json (run after build_map.py, before pack_map.py).

Input: infrastructure.parquet made by fetch_context.py (Overture base/infrastructure, from OpenStreetMap).
Traffic lights are highway=traffic_signals nodes (in Montréal mostly one per approach, a few metres before
the junction) and crossings with crossing=traffic_signals; stop signs are highway=stop. Points of the same
kind close to each other (CLUSTER_M) are grouped into one stop ("a junction with lights"), so a runner
crossing a signalised junction is charged once, however many signal nodes it has.

    python3 add_signals.py <dir with infrastructure.parquet> map-data.json

Writes into the JSON: "signals": {"kinds": [per group: 1 light, 2 stop sign],
"off": [per group: first point index, plus the end], "pts": [delta-coded x, y in the map's 1e-5 degree units]}.
"""
import sys, json, math, collections
import pyarrow.parquet as pq
import shapely

SRC, MAP = sys.argv[1], sys.argv[2]
CLUSTER_M = {1: 35, 2: 25}  # per kind; stop signs sit on short blocks, so a smaller reach keeps junctions apart
LIGHT, STOP = 1, 2

d = json.load(open(MAP, encoding="utf-8"))
LON0, LAT0 = d["origin"]
Q = d["scale"]
xmin, ymin, xmax, ymax = d["bbox"]
MX, MY = 111320 * math.cos(math.radians(d.get("lat0", 45.46))), 110540

pts = {LIGHT: [], STOP: []}
for r in pq.read_table(f"{SRC}/infrastructure.parquet", columns=["subtype", "class", "source_tags", "geometry"]).to_pylist():
    if r["subtype"] != "transportation":
        continue
    tags = dict(r["source_tags"] or [])
    cls = r["class"]
    if cls == "traffic_signals":
        if tags.get("traffic_signals") in ("emergency", "blinker", "ramp_meter", "stop_sign"):
            continue
        kind = LIGHT
    elif cls == "crossing":
        if tags.get("crossing") != "traffic_signals" and tags.get("crossing:signals") not in ("yes", "traffic_signals"):
            continue
        kind = LIGHT
    elif cls == "stop":
        kind = STOP
    else:
        continue
    g = shapely.from_wkb(r["geometry"])
    if g.geom_type != "Point" or not (xmin <= g.x <= xmax and ymin <= g.y <= ymax):
        continue
    pts[kind].append((g.x, g.y))

def cluster(P, R):
    """Single-linkage groups of points closer than CLUSTER_M (grid + union-find)."""
    xy = [((lon - LON0) * MX, (lat - LAT0) * MY) for lon, lat in P]
    parent = list(range(len(P)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    grid = collections.defaultdict(list)
    for i, (x, y) in enumerate(xy):
        grid[(int(x // R), int(y // R))].append(i)
    for (cx, cy), lst in grid.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((cx + dx, cy + dy), []):
                    for i in lst:
                        if i < j and math.dist(xy[i], xy[j]) < R:
                            parent[find(i)] = find(j)
    groups = collections.defaultdict(list)
    for i in range(len(P)):
        groups[find(i)].append(P[i])
    return list(groups.values())

kinds, off, flat = [], [0], []
px = py = 0
for kind in (LIGHT, STOP):
    gs = cluster(pts[kind], CLUSTER_M[kind])
    gs.sort(key=lambda g: (round(sum(p[1] for p in g) / len(g), 3), sum(p[0] for p in g) / len(g)))
    for g in gs:
        kinds.append(kind)
        for lon, lat in g:
            x, y = round((lon - LON0) * Q), round((lat - LAT0) * Q)
            flat += [x - px, y - py]
            px, py = x, y
        off.append(off[-1] + len(g))
    print({LIGHT: "traffic lights", STOP: "stop signs"}[kind], len(pts[kind]), "points in", len(gs), "groups")

d["signals"] = {"kinds": kinds, "off": off, "pts": flat}
d["source"] = d["source"].split(";")[0] + "; traffic lights and stop signs from Overture base/infrastructure (OpenStreetMap)"
with open(MAP, "w", encoding="utf-8") as f:
    json.dump(d, f, separators=(",", ":"), ensure_ascii=False)
print("wrote", MAP)
