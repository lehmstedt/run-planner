# Verdun Run Loops

A running-route planner that runs entirely offline inside a Claude artifact.

- Pick a distance and it builds a loop from home (default: 5e Avenue, Verdun, H4G 2Z5).
- Routing favours cycle paths and park trails over car roads (the "Path preference" slider sets how strongly).
- Drag the route line to pull it through a new point, drag a white dot to move it, tap a dot to remove it.
- "Fit to distance" rescales an edited loop back to the target; "Export GPX" saves it for a watch.

## Deploy

It's a static site (no build step), published with GitHub Pages by `.github/workflows/pages.yml`:

1. One-time setup: repo **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. Every push to `main` redeploys (or run the workflow by hand from the Actions tab).
3. The site is served at `https://<owner>.github.io/run-planner/`.

Only `index.html` and `map-data.json` are published; `scripts/` stays in the repo.

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
