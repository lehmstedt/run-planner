"""Build the offline map file (map-data.json) used by the run planner page.

Input: Overture Maps parquet extracts made by fetch_segments.py / fetch_context.py.
Output: a compact JSON (gzipped when the name ends in .gz) with a walkable routing graph, water and park polygons.

    python3 build_map.py <dir with segments/water/land_use/address.parquet> <out.json.gz>
"""
import sys, json, math, collections
import pyarrow.parquet as pq
import shapely
from shapely.geometry import box

SRC, OUT = sys.argv[1], sys.argv[2]
BBOX = (-73.74, 45.36, -73.42, 45.56)
LON0, LAT0 = BBOX[0], BBOX[1]
Q = 1e5  # 1e-5 degree units (~1 m)
HOME_POSTCODE = "H4G2Z5"

# Category ids, shared with the page.
CYCLE, TRAIL, SIDEWALK, CROSSING, QUIET, TERTIARY, SECONDARY, PRIMARY, STEPS = range(9)
CAT_NAMES = ["cycle", "trail", "sidewalk", "crossing", "quiet", "tertiary", "secondary", "primary", "steps"]


def q(lon, lat):
    return (round((lon - LON0) * Q), round((lat - LAT0) * Q))


def modes(a):
    return set((a.get("when") or {}).get("mode") or [])


def category(r):
    cls, sub = r["class"], r["subclass"]
    flags = {v for f in (r["road_flags"] or []) if not f.get("between") for v in f["values"]}
    if flags & {"is_indoor", "is_under_construction", "is_abandoned"}:
        return None
    if cls in ("motorway", "trunk") or sub in ("driveway", "parking_aisle"):
        return None
    acc = [a for a in (r["access_restrictions"] or []) if not a.get("between")]
    foot_ok = any(a["access_type"] in ("allowed", "designated") and "foot" in modes(a) for a in acc)
    bike_desig = any(a["access_type"] == "designated" and "bicycle" in modes(a) for a in acc)
    if cls != "cycleway" and not foot_ok:
        for a in acc:
            m = modes(a)
            if a["access_type"] == "denied" and (not a.get("when") or "foot" in m):
                if not any(b["access_type"] in ("allowed", "designated") and (modes(b) & {"bicycle", "foot"}) for b in acc):
                    return None
    if cls == "cycleway":
        return CROSSING if sub == "cycle_crossing" else CYCLE
    if cls == "footway":
        if sub == "sidewalk":
            return SIDEWALK
        if sub == "crosswalk":
            return CROSSING
        return CYCLE if bike_desig else TRAIL
    if cls in ("path", "track", "bridleway", "pedestrian", "living_street"):
        return CYCLE if bike_desig else TRAIL
    if cls == "steps":
        return STEPS
    if cls in ("residential", "unclassified", "service", "unknown"):
        return QUIET
    if cls == "tertiary":
        return TERTIARY
    if cls == "secondary":
        return SECONDARY
    if cls == "primary":
        return PRIMARY
    return QUIET


def mlen(a, b):
    kx = 111320 * math.cos(math.radians(45.46))
    return math.hypot((b[0] - a[0]) * kx, (b[1] - a[1]) * 110540)


def split_line(coords, cuts):
    """coords: [(lon,lat)], cuts: sorted fractions along length. Returns list of pieces between cuts."""
    seg = [mlen(coords[i], coords[i + 1]) for i in range(len(coords) - 1)]
    total = sum(seg) or 1e-9
    cum = [0.0]
    for s in seg:
        cum.append(cum[-1] + s)

    def point_at(f):
        d = f * total
        for i in range(len(seg)):
            if cum[i + 1] >= d or i == len(seg) - 1:
                t = 0 if seg[i] == 0 else min(1, max(0, (d - cum[i]) / seg[i]))
                return i, (coords[i][0] + t * (coords[i + 1][0] - coords[i][0]), coords[i][1] + t * (coords[i + 1][1] - coords[i][1]))

    pieces = []
    for f0, f1 in zip(cuts, cuts[1:]):
        i0, p0 = point_at(f0)
        i1, p1 = point_at(f1)
        pts = [p0] + [coords[k] for k in range(i0 + 1, i1 + 1)] + [p1]
        pieces.append(pts)
    return pieces


# ---------- graph ----------
segs = pq.read_table(f"{SRC}/segments.parquet").to_pylist()

# Many sidewalks are mapped as plain footways. A footway/path that runs alongside a street
# (most of its length within 18 m of one) is treated as that street for routing, and drawn as a sidewalk.
MX, MY = 111320 * math.cos(math.radians(45.46)), 110540
ROAD_CAT = {"residential": QUIET, "unclassified": QUIET, "living_street": QUIET, "service": QUIET,
            "tertiary": TERTIARY, "secondary": SECONDARY, "primary": PRIMARY, "motorway": PRIMARY, "trunk": PRIMARY}

def to_m(coords):
    return [((lon - LON0) * MX, (lat - LAT0) * MY) for lon, lat in coords]

road_geoms, road_cats = [], []
for r in segs:
    if r["class"] in ROAD_CAT and r["subclass"] not in ("driveway", "parking_aisle"):
        g = shapely.from_wkb(r["geometry"])
        if g.geom_type == "LineString":
            road_geoms.append(shapely.LineString(to_m(g.coords)))
            road_cats.append(ROAD_CAT[r["class"]])
tree = shapely.STRtree(road_geoms)
SIDE = 10  # sidewalk flag added to the category byte

def alongside_road(coords):
    line = shapely.LineString(to_m(coords))
    n = max(2, int(line.length // 10) + 1)
    pts = shapely.line_interpolate_point(line, [i / (n - 1) for i in range(n)], normalized=True)
    idx = tree.query_nearest(pts, max_distance=18, all_matches=False)
    hit = collections.Counter(road_cats[j] for j in idx[1])
    if sum(hit.values()) >= 0.6 * n:
        return max(hit.items(), key=lambda kv: (kv[0] >= TERTIARY, kv[1]))[0]  # busiest frequent neighbour
    return None
names, name_idx = [""], {"": 0}
node_idx, node_xy = {}, []
edges = []  # [a, b, cat, name, pts(quantized)]
dropped = collections.Counter()

for r in segs:
    cat = category(r)
    if cat is None:
        dropped[r["class"]] += 1
        continue
    g = shapely.from_wkb(r["geometry"])
    if g.geom_type != "LineString":
        continue
    coords = list(g.coords)
    if cat in (TRAIL, SIDEWALK) and r["class"] in ("footway", "path", "pedestrian"):
        near = alongside_road(coords)
        if near is not None:
            cat = SIDE + near
        elif cat == SIDEWALK:
            cat = SIDE + QUIET
    cons = sorted((c["at"], c["connector_id"]) for c in (r["connectors"] or []))
    if len(cons) < 2:
        continue
    nm = (r["names"] or {}).get("primary") or ""
    if nm not in name_idx:
        name_idx[nm] = len(names)
        names.append(nm)
    pieces = split_line(coords, [c[0] for c in cons])
    for (fa, ca), (fb, cb), pts in zip(cons, cons[1:], pieces):
        qp = [q(*p) for p in pts]
        for cid, p in ((ca, qp[0]), (cb, qp[-1])):
            if cid not in node_idx:
                node_idx[cid] = len(node_xy)
                node_xy.append(p)
        a, b = node_idx[ca], node_idx[cb]
        qp[0], qp[-1] = node_xy[a], node_xy[b]
        # drop consecutive duplicates
        dd = [qp[0]] + [p for i, p in enumerate(qp[1:], 1) if p != qp[i - 1]]
        if a == b and len(dd) < 3:
            continue
        edges.append([a, b, cat, name_idx[nm], dd])

print("raw nodes", len(node_xy), "edges", len(edges), "dropped", dict(dropped))

# ---------- home ----------
addr = [r for r in pq.read_table(f"{SRC}/address.parquet").to_pylist()
        if (r["postcode"] or "").replace(" ", "").upper() == HOME_POSTCODE]
hx = sum(shapely.from_wkb(r["geometry"]).x for r in addr) / len(addr)
hy = sum(shapely.from_wkb(r["geometry"]).y for r in addr) / len(addr)
street = collections.Counter(r["street"] for r in addr).most_common(1)[0][0]
nums = sorted(int("".join(ch for ch in r["number"] if ch.isdigit())) for r in addr if any(ch.isdigit() for ch in r["number"]))
home = {"lon": round(hx, 6), "lat": round(hy, 6), "label": f"{nums[0]}–{nums[-1]} {street}, H4G 2Z5"}
print("home", home)

# ---------- largest component ----------
adj = collections.defaultdict(list)
for i, e in enumerate(edges):
    adj[e[0]].append(i)
    adj[e[1]].append(i)
comp = [-1] * len(node_xy)
sizes = []
for s in range(len(node_xy)):
    if comp[s] != -1 or s not in adj:
        continue
    cid, stack, n = len(sizes), [s], 0
    comp[s] = cid
    while stack:
        u = stack.pop()
        n += 1
        for ei in adj[u]:
            e = edges[ei]
            v = e[1] if e[0] == u else e[0]
            if comp[v] == -1:
                comp[v] = cid
                stack.append(v)
    sizes.append(n)
main = max(range(len(sizes)), key=lambda c: sizes[c])
edges = [e for e in edges if comp[e[0]] == main]
print("main component nodes", sizes[main], "edges", len(edges))

# ---------- contract degree-2 nodes with same cat+name ----------
def contract(edges):
    adj = collections.defaultdict(list)
    for i, e in enumerate(edges):
        adj[e[0]].append(i)
        if e[1] != e[0]:
            adj[e[1]].append(i)
    alive = [True] * len(edges)
    for n, lst in list(adj.items()):
        lst = [i for i in lst if alive[i]]
        if len(lst) != 2:
            continue
        i, j = lst
        ei, ej = edges[i], edges[j]
        if i == j or ei[2] != ej[2] or ei[3] != ej[3] or ei[0] == ei[1] or ej[0] == ej[1]:
            continue
        # orient ei to end at n, ej to start at n
        pi = ei[4] if ei[1] == n else ei[4][::-1]
        ai = ei[0] if ei[1] == n else ei[1]
        pj = ej[4] if ej[0] == n else ej[4][::-1]
        bj = ej[1] if ej[0] == n else ej[0]
        if ai == bj:
            continue
        edges[i] = [ai, bj, ei[2], ei[3], pi + pj[1:]]
        alive[j] = False
        for k, x in enumerate(adj[bj]):
            if x == j:
                adj[bj][k] = i
        for k, x in enumerate(adj[ai]):
            if x == j:
                adj[ai][k] = i
        adj[n] = []
    return [e for e, a in zip(edges, alive) if a]

edges = contract(edges)

# Simplify polylines (Douglas-Peucker, ~1.5 m) keeping endpoints.
def dp(pts, tol=1.5):
    if len(pts) < 3:
        return pts
    ls = shapely.LineString(pts).simplify(tol, preserve_topology=False)
    out = [tuple(map(round, c)) for c in ls.coords]
    out[0], out[-1] = pts[0], pts[-1]
    return out

# reindex nodes
used = sorted({e[0] for e in edges} | {e[1] for e in edges})
remap = {n: i for i, n in enumerate(used)}
nodes_out = []
for n in used:
    nodes_out += list(node_xy[n])
edges_out, geom_out = [], []
kx = math.cos(math.radians(45.46)) * 1.1132  # metres per unit (x)
ky = 1.1054
for e in edges:
    pts = dp(e[4])
    length = sum(math.hypot((b[0] - a[0]) * kx, (b[1] - a[1]) * ky) for a, b in zip(pts, pts[1:]))
    edges_out += [remap[e[0]], remap[e[1]], e[2], e[3], round(length, 1)]
    inner = pts[1:-1]
    flat, px, py = [], pts[0][0], pts[0][1]
    for x, y in inner:
        flat += [x - px, y - py]
        px, py = x, y
    geom_out.append(flat)
print("final nodes", len(used), "edges", len(edges))

# ---------- background polygons ----------
clip = box(*BBOX)

def enc_poly(g, tol):
    out = []
    g = g.intersection(clip)
    if g.is_empty:
        return out
    g = shapely.simplify(g, tol, preserve_topology=True)
    polys = [g] if g.geom_type == "Polygon" else [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon"]
    for p in polys:
        if p.area < (tol * 4) ** 2:
            continue
        rings = []
        for ring in [p.exterior] + list(p.interiors):
            flat, px, py = [], 0, 0
            for lon, lat in list(ring.coords)[:-1]:
                x, y = q(lon, lat)
                flat += [x - px, y - py]
                px, py = x, y
            if len(flat) >= 6:
                rings.append(flat)
        if rings:
            out.append(rings)
    return out

water = []
for r in pq.read_table(f"{SRC}/water.parquet").to_pylist():
    if r["subtype"] == "human_made":
        continue
    g = shapely.from_wkb(r["geometry"])
    if g.geom_type in ("Polygon", "MultiPolygon"):
        water += enc_poly(g, 0.00003)

GREEN = {("park", "park"), ("park", "dog_park"), ("recreation", "recreation_ground"), ("golf", "golf_course"),
         ("winter_sports", "nordic"), ("managed", "grass"), ("recreation", "pitch"), ("horticulture", "garden"),
         ("park", "nature_reserve"), ("protected", "nature_reserve"), ("recreation", "playground")}
parks = []
for r in pq.read_table(f"{SRC}/land_use.parquet").to_pylist():
    if (r["subtype"], r["class"]) not in GREEN and r["subtype"] not in ("park", "golf"):
        continue
    g = shapely.from_wkb(r["geometry"])
    if g.geom_type in ("Polygon", "MultiPolygon"):
        parks += enc_poly(g, 0.00002)
print("water polys", len(water), "park polys", len(parks))

data = {
    "source": "Overture Maps Foundation (includes OpenStreetMap data, ODbL) release 2026-11-18.0",
    "origin": [LON0, LAT0], "scale": Q, "bbox": BBOX,
    "home": home,
    "cats": CAT_NAMES,
    "names": names,
    "nodes": nodes_out,
    "edges": edges_out,
    "geom": geom_out,
    "water": water,
    "parks": parks,
}
import gzip, os
raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode()
with (gzip.open(OUT, "wb", 9) if OUT.endswith(".gz") else open(OUT, "wb")) as f:
    f.write(raw)
print("json", len(raw) // 1024, "KB")
print("wrote", OUT, os.path.getsize(OUT) // 1024, "KB")
