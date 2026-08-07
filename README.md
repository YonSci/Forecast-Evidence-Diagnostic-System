# Forecast Evidence and Diagnostic System

A web app testing whether NMME's Kiremt/JJAS 2026 rainfall forecast for Ethiopia and the
Greater Horn of Africa is physically consistent with atmospheric circulation and ocean-state
drivers — across three real NMME initialization cycles (May, June, July 2026).

This repo has three parts:

- **`scripts/`, `config/`, `data/`, `outputs/`** — the original Python data pipeline (NMME/ERA5/CFSv2
  download, organization, anomaly computation, evidence scoring, map rendering). Scripts are
  numbered in run order; `01`-`12` are the original May-init pipeline, `13`-`22` extend it with
  June-init, July-init, and Leaflet-ready overlay rasters.
- **`backend/`** — a FastAPI service that reads the pipeline's own output CSVs and pre-rendered
  map images (curated into `backend/app/static_data/`, since the deploy host won't have the
  full local `outputs/` tree) and serves them as a JSON API.
- **`frontend/`** — a React + Vite app (React Router, react-leaflet, Recharts) that consumes
  that API.

## Architecture

```
Frontend (Vercel)                    Backend (Render)
React + React Router + Vite    --->  FastAPI + Uvicorn
react-leaflet (maps)                 reads backend/app/static_data/
Recharts (charts)                      tables/*.csv   (pipeline output CSVs)
                                        overlays/*.png (geo-referenced anomaly rasters)
                                        gallery/*.png  (report-style diagnostic figures)
```

The Leaflet map on the Anomaly Evidence tab renders the pipeline's precipitation-anomaly
rasters as geo-referenced `<ImageOverlay>` layers (positioned by their real lat/lon bounding
box) over a CartoDB Positron basemap — not a custom tile server.

## Local development

**Backend**

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate     # or source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # adjust FRONTEND_ORIGIN if your Vite port differs from 5173
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for the interactive API reference.

**Frontend** (separate terminal)

```bash
cd frontend
npm install
cp .env.example .env.local   # VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

Visit the printed local URL (usually `http://localhost:5173`).

**Refreshing the backend's static data** — if the pipeline scripts produce new outputs
(a new initialization cycle, updated CSVs), re-run the curation step to pull the latest
curated copy into `backend/app/static_data/`:

```bash
pip install -r backend/requirements-dev.txt   # adds Pillow, only needed for this script
python backend/scripts/sync_static_data.py
```

## Deploying

You'll need your own GitHub, Vercel, and Render accounts — none of that is set up in this
repo yet.

1. **Push to GitHub**
   ```bash
   git remote add origin <your-repo-url>
   git push -u origin main
   ```

2. **Backend on Render**
   - New Web Service → connect this repo.
   - Render should pick up `backend/render.yaml` automatically (it sets root dir `backend`,
     build command `pip install -r requirements.txt`, start command
     `uvicorn app.main:app --host 0.0.0.0 --port $PORT`). If it doesn't auto-detect, set those
     fields manually with root directory `backend`.
   - After the first deploy, note the service URL (e.g. `https://forecast-evidence-api.onrender.com`).
   - Leave `FRONTEND_ORIGIN` as-is for now — you'll update it in step 4.

3. **Frontend on Vercel**
   - New Project → import this repo, set **root directory** to `frontend`.
   - Vercel auto-detects the Vite framework from `frontend/vercel.json`.
   - Add an environment variable: `VITE_API_BASE_URL` = your Render URL from step 2.
   - Deploy. Note the resulting Vercel URL (e.g. `https://your-app.vercel.app`).

4. **Close the loop** — go back to the Render service's environment variables and set
   `FRONTEND_ORIGIN` to your Vercel URL (comma-separate if you also want to keep
   `http://localhost:5173` for local testing against the deployed API):
   ```
   FRONTEND_ORIGIN=https://your-app.vercel.app,http://localhost:5173
   ```
   Redeploy the backend for the CORS change to take effect.

5. **Verify** — open the Vercel URL, go to the Anomaly Evidence tab, and confirm the map and
   charts load real data (not stuck on "Loading…", which usually means the `VITE_API_BASE_URL`
   or `FRONTEND_ORIGIN` values don't match).

## Known caveats

- **react-router-dom** currently carries an upstream advisory
  ([GHSA-qwww-vcr4-c8h2](https://github.com/advisories/GHSA-qwww-vcr4-c8h2)) scoped to React
  Server Components mode. This app is a plain client-side SPA and doesn't use RSC, so the
  advisory doesn't apply here — but re-check before adopting RSC features later.
- Only three initialization cycles are wired up (May/June/July 2026). Each successive cycle
  covers a narrower set of forecast months, since NMME real-time anomaly products skip the
  partially-elapsed initialization month (see the Methodology tab, or `scripts/13`-`22`'s
  docstrings, for the verification behind that).
- The Atmospheric, Oceanic, and Integrated Evidence Matrix tabs are only backed by the
  May-init pipeline run (CFSv2/ERA5/evidence-scoring wasn't recomputed for June/July) — this is
  surfaced in the UI, not hidden.
- This is a research-grade diagnostic tool, not an official seasonal outlook. See the
  Methodology tab / `/api/methodology/limitations` for the full list.
