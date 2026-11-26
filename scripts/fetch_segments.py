import sys, pyarrow as pa, pyarrow.parquet as pq, overture
import regions
BBOX = regions.R["bbox"]
cols = ["id","names","subtype","class","subclass","connectors","road_flags","access_restrictions","geometry","bbox"]
ts = list(overture.read_bbox("transportation", "segment", BBOX, cols))
t = pa.concat_tables(ts)
t = t.filter(pa.compute.equal(t.column("subtype"), "road"))
pq.write_table(t, sys.argv[1])
print("rows", t.num_rows)
