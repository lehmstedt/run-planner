# Verdun Run Loops

A running-route planner that runs entirely offline inside a Claude artifact.

- Pick a distance and it builds a loop from home (default: 5e Avenue, Verdun, H4G 2Z5).
- Routing favours cycle paths and park trails over car roads (the "Path preference" slider sets how strongly).
- Drag the route line to pull it through a new point, drag a white dot to move it, tap a dot to remove it.
- "Fit to distance" rescales an edited loop back to the target; "Export GPX" saves it for a watch.

## Files

- `index.html` – the app (canvas map + A* routing in the browser).
- `map-data.json` – the routing graph, water and parks for Verdun, Sud-Ouest, Nuns' Island and downtown.
- `scripts/` – rebuilds `map-data.json` from Overture Maps (OpenStreetMap-based) GeoParquet on AWS Open Data:

```
pip install pyarrow requests shapely
python3 scripts/fetch_segments.py /tmp/osm/segments.parquet
python3 scripts/fetch_context.py /tmp/osm
python3 scripts/build_map.py /tmp/osm map-data.json
```

Footpaths that run alongside a street are treated as that street (sidewalks), so they don't count as trails.

Map data © OpenStreetMap contributors (ODbL), via Overture Maps.
