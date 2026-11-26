# Run Loops

A running-route planner that runs entirely offline, in a Claude artifact or as an app installed on your phone.

Two areas, picked under "Area" in the side panel: **Verdun** (Montréal; start 5e Avenue, H4G 2Z5) and **Saint-Berthevin** (Mayenne, France; start Avenue Saint-Exupéry, 53940, with Laval and the countryside around). Each area keeps its own start, settings and current loop; saved loops are listed in the area they were made in.

- Pick a distance and it builds a loop from home.
- Routing favours cycle paths and park trails over car roads (the "Path preference" slider sets how strongly).
- Loops have as few corners as possible: the router will run about 300 m further to avoid a right-angle turn, loops are ranked by corners per km, half the candidate loops use one via point less, and free via points slide to where the route runs straight through them (without leaving the target distance). Direction changes are measured across short connectors, so crossing a street to carry on the same way isn't a corner, while turning back (a hairpin, or crossing to the other sidewalk to come back the way you came) costs a lot, also where one leg hands over to the next. The loop summary counts corners and turn-backs.
- Fewer interruptions: loops avoid traffic lights (junctions and signalised crossings) and, less strongly, stop signs. "Avoid traffic lights" sets how much further the router will run to skip one (up to 600 m per light at full, a fifth of that per stop sign; 70% by default). Lights are only charged where you cross or run through the junction: running past it on a sidewalk is free. The loop summary counts traffic lights and stop signs, and the lights on the loop show as red dots when zoomed in. Skipping lights often means a few more corners through quiet side streets; slide it down to trade back.
- On phones the controls are a bottom sheet: distance and the loop buttons stay visible; tap or swipe up "More options" for the rest, touch the map to fold it away.
- Drag the route line to pull it through a new point (up to 9 points, the most a Google Maps link takes), drag a white dot to move it, tap a dot to remove it.
- "Fit to distance" rescales an edited loop back to the target; "Export GPX" saves it for a watch; "Export for My Maps" saves a KML file (styled route, start pin, km markers) to import into Google My Maps (Create a new map → Import).
- "Open in Google Maps" opens the loop as a walking itinerary: home → your points, plus extra stops on the longest stretches to make 9 → home. Google allows at most 9 stops per link, so a loop has at most 9 points (adding a 10th is refused); a loop with more (e.g. an older saved one) is flagged under the export buttons. Google picks its own streets between stops, so long loops may differ slightly from the planned one; use GPX for an exact track.
- "Saved loops" keeps named itineraries (start, via points, target distance, path preference). On claude.ai they are stored privately per signed-in person; opened anywhere else they fall back to this browser's storage. Tap one to reopen it, × to delete (with Undo).

## Install on a phone

Open the GitHub Pages site in Chrome on Android, then tap **Install app** in the side panel (or Chrome menu → **Install app** / **Add to Home screen**). The installed app opens full screen and works offline: the page, the map and the fonts are cached by `sw.js` after the first visit.

## Deploy

It's a static site (no build step), published with GitHub Pages by `.github/workflows/pages.yml`:

1. One-time setup: repo **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. Every push to `main` redeploys (or run the workflow by hand from the Actions tab).
3. The site is served at `https://<owner>.github.io/run-planner/`.

Published: `index.html`, `map-data.bin`, `map-data-*.bin`, `manifest.webmanifest`, `sw.js` and `icons/`; `scripts/` and `map-data.json` stay in the repo.

## Files

- `index.html` – the app (canvas map + A* routing in the browser). The base map is drawn once into cached tiles per zoom level, so panning and pinching only copy images.
- `map-data.bin` – what the app loads: the routing graph, traffic lights and stop signs, water and parks for southwest Montréal, downtown, the Plateau and the islands (about 25 × 22 km, enough for marathon loops), as gzipped delta-coded typed arrays (2.8 MB).
- `map-data.json` – the same data as JSON, the source `map-data.bin` is packed from.
- `manifest.webmanifest`, `sw.js`, `icons/` – make it an installable, offline app.
- `scripts/` – rebuilds the map from Overture Maps (OpenStreetMap-based) GeoParquet on AWS Open Data:

```
pip install pyarrow requests shapely numpy
cd scripts
export RUN_REGION=verdun   # or st-berthevin (areas are listed in scripts/regions.py)
python3 fetch_segments.py /tmp/osm/segments.parquet
python3 fetch_context.py /tmp/osm
python3 build_map.py /tmp/osm ../map-data.json 2026-11-18.0   # Saint-Berthevin: ../map-data-st-berthevin.json
python3 add_signals.py /tmp/osm ../map-data.json
python3 pack_map.py ../map-data.json ../map-data.bin
```

To add an area: add it to `scripts/regions.py` (bounding box, latitude, where to find the start address) and to `AREAS` in `index.html`, then build its `map-data-<id>.bin`.

After changing `map-data.bin`, bump `VERSION` in `sw.js` so installed apps download the new map.

Footpaths that run alongside a street are treated as that street (sidewalks), so they don't count as trails.

Map data © OpenStreetMap contributors (ODbL), via Overture Maps.
