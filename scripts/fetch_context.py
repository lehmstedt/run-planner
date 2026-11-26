import sys, pyarrow as pa, pyarrow.parquet as pq, overture
import regions
BBOX = regions.R["bbox"]
out = sys.argv[1]
for theme, typ, cols in [("base","water",["id","subtype","class","geometry","bbox"]),
                         ("base","land_use",["id","subtype","class","geometry","bbox"]),
                         ("addresses","address",["id","postcode","street","number","geometry","bbox"]),
                         ("base","infrastructure",["id","subtype","class","source_tags","geometry","bbox"])]:
    bb = BBOX if typ != "address" else regions.R["address_bbox"]
    ts = list(overture.read_bbox(theme, typ, bb, cols))
    t = pa.concat_tables(ts) if ts else None
    if t is not None and typ == "infrastructure":  # keep traffic lights, signalised crossings and stop signs
        t = t.filter(pa.compute.is_in(t.column("class"), pa.array(["traffic_signals", "crossing", "stop"])))
    if t is not None:
        pq.write_table(t, f"{out}/{typ}.parquet"); print(typ, t.num_rows)
