# Verdun Run Loops

A running-route planner that runs entirely offline, in a Claude artifact or as an app installed on your phone.

- Pick a distance and it builds a loop from home (default: 5e Avenue, Verdun, H4G 2Z5).
- Routing favours cycle paths and park trails over car roads (the "Path preference" slider sets how strongly).
- Drag the route line to pull it through a new point, drag a white dot to move it, tap a dot to remove it.
- "Fit to distance" rescales an edited loop back to the target; "Export GPX" saves it for a watch; "Export for My Maps" saves a KML file (styled route, start pin, km markers) to import into Google My Maps (Create a new map → Import).
- "Open in Google Maps" opens the loop as a walking itinerary (home → 9 stops spread along the loop → home). Google allows at most 9 stops per link and picks its own streets between them, so long loops may differ slightly from the planned one; use GPX for an exact track.
- "Saved loops" keeps named itineraries (start, via points, target distance, path preference). On claude.ai they are stored privately per signed-in person; opened anywhere else they fall back to this browser's storage. Tap one to reopen it, × to delete (with Undo).

## Install on a phone

Open the GitHub Pages site in Chrome on Android, then tap **Install app** in the side panel (or Chrome menu → **Install app** / **Add to Home screen**). The installed app opens full screen and works offline: the page, the map and the fonts are cached by `sw.js` after the first visit.

## Deploy

It's a static site (no build step), published with GitHub Pages by `.github/workflows/pages.yml`:

1. One-time setup: repo **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. Every push to `main` redeploys (or run the workflow by hand from the Actions tab).
3. The site is served at `https://<owner>.github.io/run-planner/`.

Published: `index.html`, `map-data.bin`, `manifest.webmanifest`, `sw.js` and `icons/`; `scripts/` and `map-data.json` stay in the repo.

## Files

- `index.html` – the app (canvas map + A* routing in the browser). The base map is drawn once into cached tiles per zoom level, so panning and pinching only copy images.
- `map-data.bin` – what the app loads: the routing graph, water and parks for southwest Montréal, downtown, the Plateau and the islands (about 25 × 22 km, enough for marathon loops), as gzipped delta-coded typed arrays (2.7 MB).
- `map-data.json` – the same data as JSON, the source `map-data.bin` is packed from.
- `manifest.webmanifest`, `sw.js`, `icons/` – make it an installable, offline app.
- `scripts/` – rebuilds the map from Overture Maps (OpenStreetMap-based) GeoParquet on AWS Open Data:

```
pip install pyarrow requests shapely
python3 scripts/fetch_segments.py /tmp/osm/segments.parquet
python3 scripts/fetch_context.py /tmp/osm
python3 scripts/build_map.py /tmp/osm map-data.json
python3 scripts/pack_map.py map-data.json map-data.bin
```

After changing `map-data.bin`, bump `VERSION` in `sw.js` so installed apps download the new map.

Footpaths that run alongside a street are treated as that street (sidewalks), so they don't count as trails.

Map data © OpenStreetMap contributors (ODbL), via Overture Maps.
