"""Pack map-data.json into the binary file the page loads (map-data.bin).

The page reads typed arrays straight out of this file, so phones skip parsing
12 MB of JSON and building hundreds of thousands of small arrays.

    python3 pack_map.py map-data.json map-data.bin

Layout (the whole file is gzipped):
    "RPL1" | uint32 meta length | meta JSON (padded to 4 bytes) | arrays, each padded to 4 bytes
meta["arrays"] lists [name, dtype, length] in file order. Coordinates stay in the
JSON's 1e-5 degree units, delta-coded; the page converts them to metres.
"""
import sys, json, gzip, math, struct
import numpy as np

SRC, OUT = sys.argv[1], sys.argv[2]
d = json.load(open(SRC, encoding="utf-8"))

kx = math.cos(d.get("lat0", 45.46) * math.pi / 180) * 111320 / d["scale"]
ky = 110540 / d["scale"]

# Everything stays in the JSON's integer units (1e-5 degree, ~1 m) and is delta-coded, which
# gzips far better than floats; the page turns it into metres with the same arithmetic as before.
nodes = np.asarray(d["nodes"], dtype=np.int64).reshape(-1, 2)
node_d = np.diff(nodes, axis=0, prepend=0).reshape(-1)

E = d["edges"]
m = len(E) // 5
ea = np.asarray(E[0::5], dtype=np.int64)
eb = np.asarray(E[1::5], dtype=np.int64)
ea_d = np.diff(ea, prepend=0)          # page: ea[i] = ea[i-1] + ea_d[i]
eb_d = eb - ea                          # page: eb[i] = ea[i] + eb_d[i]
ecode = np.asarray(E[2::5], dtype=np.uint8)
en = np.asarray(E[3::5], dtype=np.uint16)
el_dm = np.rint(np.asarray(E[4::5], dtype=np.float64) * 10).astype(np.uint32)  # decimetres
assert np.allclose(el_dm / 10, E[4::5]), "edge lengths must have one decimal"
assert len(d["names"]) < 65536


def flat_lists(lst):
    off = np.zeros(len(lst) + 1, dtype=np.uint32)
    off[1:] = np.cumsum([len(f) // 2 for f in lst])
    vals = np.fromiter((v for f in lst for v in f), dtype=np.int64, count=2 * int(off[-1]))
    return off, vals


goff, gdel = flat_lists(d["geom"])      # inner points, delta-coded from the edge's first node
gtype = np.int16 if np.abs(gdel).max() < 32768 else np.int32


def polys(lst):
    poff = np.zeros(len(lst) + 1, dtype=np.uint32)
    poff[1:] = np.cumsum([len(p) for p in lst])
    roff, vals = flat_lists([r for p in lst for r in p])
    return poff, roff, vals


wpoff, wroff, wdel = polys(d["water"])
ppoff, proff, pdel = polys(d["parks"])

arrays = [
    ("nodeD", node_d.astype(np.int32)), ("eaD", ea_d.astype(np.int32)), ("ebD", eb_d.astype(np.int32)),
    ("elDm", el_dm), ("goff", goff),
    ("waterPoly", wpoff), ("waterRing", wroff), ("waterD", wdel.astype(np.int32)),
    ("parkPoly", ppoff), ("parkRing", proff), ("parkD", pdel.astype(np.int32)),
    ("gD", gdel.astype(gtype)), ("en", en), ("ecode", ecode),
]
if "signals" in d:  # traffic lights and stop signs (add_signals.py): groups of points
    sg = d["signals"]
    arrays += [("sigOff", np.asarray(sg["off"], dtype=np.uint32)), ("sigD", np.asarray(sg["pts"], dtype=np.int32)),
               ("sigK", np.asarray(sg["kinds"], dtype=np.uint8))]
meta = {k: d[k] for k in ("source", "origin", "scale", "bbox", "home", "cats", "names")}
meta.update(kx=kx, ky=ky, n=len(nodes), m=m,
            arrays=[[name, a.dtype.name, int(a.size)] for name, a in arrays])
mj = json.dumps(meta, separators=(",", ":"), ensure_ascii=False).encode()
mj += b" " * (-len(mj) % 4)

body = bytearray(b"RPL1" + struct.pack("<I", len(mj)) + mj)
for _, a in arrays:
    body += a.astype(a.dtype.newbyteorder("<")).tobytes()
    body += b"\0" * (-len(body) % 4)

packed = gzip.compress(bytes(body), 9, mtime=0)
with open(OUT, "wb") as f:
    f.write(packed)
print(f"{OUT}: {len(body) / 1e6:.1f} MB raw, {len(packed) / 1e6:.1f} MB gzipped")
