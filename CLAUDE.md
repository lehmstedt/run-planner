# Workflow

After finishing every feature request:

1. Commit and push the work to `main` (the session branch too, if one is required).
2. Republish the live artifact https://claude.ai/artifact/XYQKTyso1iPeWNyVZcQGS8 from `index.html`
   (read it first with the Artifact tool, then publish with that `url`). The artifact serves the map as
   `map-data.bin.wasm` (artifacts don't serve `.bin`; same bytes as `map-data.bin`); it is already
   published there and only needs re-uploading when `map-data.bin` changes.
