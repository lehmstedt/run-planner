# Verdun Run Loops

A running-route planner that runs entirely offline inside a Claude artifact.

- Pick a distance and it builds a loop from home (default: 5e Avenue, Verdun, H4G 2Z5).
- Routing favours cycle paths and park trails over car roads (the "Path preference" slider sets how strongly).
- Drag the route line to pull it through a new point, drag a white dot to move it, tap a dot to remove it.
- "Fit to distance" rescales an edited loop back to the target; "Export GPX" saves it for a watch.

## Deploy

It's a static site (no build step), so any static host works. On Vercel:

1. vercel.com → Add New → Project → import this GitHub repo.
2. Framework preset: **Other**. Leave the build command and output directory empty.
3. Deploy. Each push to the production branch redeploys.

Or from a terminal: `npx vercel` (preview) / `npx vercel --prod`.
`vercel.json` caches `map-data.json` for a day; `.vercelignore` keeps `scripts/` out of the deployment.

## Files

- `index.html` – the app (canvas map + A* routing in the browser).
- `map-data.json` – the routing graph, water and parks for southwest Montréal, downtown, the Plateau and the islands (about 25 × 22 km, enough for marathon loops).
- `scripts/` – rebuilds `map-data.json` from Overture Maps (OpenStreetMap-based) GeoParquet on AWS Open Data:

```
pip install pyarrow requests shapely
python3 scripts/fetch_segments.py /tmp/osm/segments.parquet
python3 scripts/fetch_context.py /tmp/osm
python3 scripts/build_map.py /tmp/osm map-data.json
```

Footpaths that run alongside a street are treated as that street (sidewalks), so they don't count as trails.

Map data © OpenStreetMap contributors (ODbL), via Overture Maps.
