# Astronaut Photography Prediction & Analysis

**Latest local release (12 November 2026):** 2,275 native-pixel photo overlays, paired satellite comparisons, matched-region percentage-error filtering, full-search exports, and a first-visit tutorial. The public release requires hosting the 9.24 GB overlay package and setting `VITE_NATIVE_CATALOG_BASE`; see [current deployment requirements](docs/deployment.md). The historical sample and API setup below remain as reference.

An API-connected research dashboard built from the existing Vercel prototype. The verified local dataset contains 9,801 real astronaut photos: the 2,130-photo original benchmark plus 7,671 Mediterranean test photos from Johann’s catalog exports. Together they provide 19,602 frozen chlorophyll-a/Kd(490) estimates and 4,754 quality-masked MODIS Aqua Level-2 matchups; 5,047 Mediterranean photos are explicitly inference-only. Additional inference runs append results rather than replacing the benchmark.

See [feature decisions](docs/feature-decisions.md) for what works now, what needs processing, and which mock claims were removed. APPA’s cloud destination is **APPA Sample** (`qcjkgrelvnivgpfwrfan`) in your Free organization. The cloud sample contains 100 photos and 50 references, with original and subsequent model estimates preserved; the larger archive remains local. Johann’s project is read-only source data.

## Run locally

From this directory, with the NASA model workspace beside it:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm ci
./scripts/dev.sh
```

Open **http://127.0.0.1:5173**. API docs are at **http://127.0.0.1:8000/api/docs**. The dev script uses SQLite unless DATABASE_URL is explicitly exported and disables inference by default. It imports both saved cohorts idempotently. SQLite data is stored in ignored `runtime/dashboard.db`, outside the frontend build. Back this file up with SQLite's backup API while the application is active.

Local `.env` accepts literal `KEY=VALUE` settings (optionally quoted); process environment values take precedence. No shell interpolation is performed. PostgreSQL URLs must URL-encode special password characters.

The existing NASA ML environment is used for checkpoint execution:

```sh
PYTHONPATH=backend LOKY_MAX_CPU_COUNT=4 ../kd490_proposal/.venv/bin/python -m app.worker
```

The worker needs NumPy, pandas, Pillow, joblib, scikit-learn, scipy, torch, torchvision, threadpoolctl, requests, and SQLAlchemy. Use the frozen training environment rather than silently upgrading checkpoint dependencies. The API environment intentionally does not load Torch.

### Queue inference

Set a strong `OPERATOR_API_KEY` in ignored `.env` or the API process environment **before starting it**, then enter that key in the dashboard's inference dialog. Set `INFERENCE_ENABLED=1` only while a compatible supervised worker is running. Never use a `VITE_` prefix for secrets. The key is not retained by the browser. Without it, API mutations fail closed; reads still work. The worker must use the same `DATABASE_URL` and `NASA_WORKSPACE` as the importer.

An operator can alternatively use the local CLI, which accesses the database directly:

```sh
# Copy exact model IDs from /api/models, not model display names.
PYTHONPATH=backend .venv/bin/python -m app.catalog queue \
  --image-id ISS005-E-11615 \
  --model-id YOUR_CHLOR_MODEL_ID --model-id YOUR_KD_MODEL_ID \
  --batch-key my-first-batch
```

Repeat `--image-id` to queue more photos. Reusing the same batch key, photo ID, and model IDs resumes without duplicate jobs. Use a new batch key for a deliberate rerun. A worker runs CPU inference from saved checkpoints; it never retrains models. Training/validation/test exposure remains attached after rerunning.

Jobs use atomic claims, ten-minute leases, and fenced completion. A crashed worker's job is reclaimed after its lease expires, up to three attempts. Model/input exceptions are terminal and recorded; inspect worker logs, fix the cause, and submit a new request. The current worker processes one photo at a time, well below the lease duration in local verification. Longer tasks will need lease heartbeats or a separate queue design.

### Add genuinely new photographs

Prepare a trusted CSV with `image_id,local_image,captured_at,latitude,longitude,cloud_percent,sun_elevation,sun_azimuth,focal_length`. Only `image_id` and `local_image` are required; missing metadata remains missing. Paths must point to PNG/JPEG files within `NASA_WORKSPACE`. Time, if present, must include its UTC offset. Known clouds above 30%, night photos, invalid coordinates, oversized images, duplicate IDs, and conflicting source bytes are rejected. Operators must verify ocean content; there is no validated automatic water mask.

```sh
PYTHONPATH=backend ../kd490_proposal/.venv/bin/python -m app.catalog ingest /path/to/catalog.csv
```

Then queue those image IDs with the CLI or dashboard. No satellite labels are required for inference. New images have no satellite comparison until a verified matchup is ingested. Existing photo metadata is not silently overwritten. Browser uploads and automated new satellite extraction are not implemented in this release.

## Implemented experience

- Server-side search, date/mission/split filters, satellite/prediction availability, stable pagination and sort.
- Unaltered source photos, scalar estimates, model versions, matchup quality, signed differences and lineage.
- Versioned run/job history and authenticated inference requests.
- JSON export, browser-local collection, side-by-side comparison and geographic map links.
- Real empty/error/loading states; no fallback to sample data.
- Calibrated Kd(490) confidence percentages for supported outputs, including photos without satellite references. The chlorophyll confidence candidate failed validation and was not published; its existing estimates remain available. Unsupported scores stay unavailable.
- Model sensitivity overlays and approximate satellite comparisons in the explanation pilot. Automatic segmentation, clarity classes and usefulness scores remain unavailable.

## Verify

```sh
.venv/bin/python -m pip install -r backend/requirements-dev.txt
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v
PYTHONPATH=backend LOKY_MAX_CPU_COUNT=4 ../kd490_proposal/.venv/bin/python -m unittest discover -s backend/tests -p test_inference_replay.py -v
npm run build
```

The checkpoint test compares 18 newly computed outputs across nine train/validation/test photos with their frozen exports, at relative tolerance `1e-5`. This tests serving parity, not new scientific accuracy. Run it against the initial imported benchmark. The API suite uses isolated temporary databases. For a fresh PostgreSQL destination, use `backend/schema-bootstrap.sql`; v2 deployments use the additive `backend/schema-v3.sql`. Verify live deployment separately from the local checks.

## Production

See [current sample release status](docs/sample-release-2026-11-03.md), [deployment](docs/deployment.md), and the [dashboard data contract](docs/data-contract.md). The new Free APPA Sample database contains the verified 100-photo sample (975,774 serialized bytes; about 13 MB total database size after import). Every imported row was checked against its source. The importer permits at most 100 photos and 2 MiB, excludes image bytes and overlays, and uses paced batches. The old review project is preserved; its recovery ticket is separate.

The public dashboard uses the FastAPI API at `https://appa-api.vercel.app`, with the frontend at `https://astronautphotographypredictionanaly.vercel.app`. New inference and operator writes are disabled. The frontend hosts verified compressed previews of the 100 registered sample crops as static assets; image bytes stay out of Supabase. The API retains a NASA-original fallback for other clients.

## Spatial layers and uncertainty

The public pilot shows occlusion sensitivity from the exact model checkpoint and, when available, a quality-masked satellite reference projected approximately onto the photo. Sensitivity explains changes in the whole-crop estimate; it is not a local concentration map. Photos without references can still have model explanations.

Confidence percentages estimate the chance of being within ±25% of the satellite-reference definition. Fresh models reserve separate calibration scenes, and scores are served only for reliability bands that pass the frozen evaluation checks. No satellite value from the current photo is needed. See [confidence release and limitations](docs/confidence-release-2026-11-03.md). Arbitrary new uploads and confidence-enabled queue inference are not yet exposed by the public sample.

The separate experimental spatial and conformal-interval tools remain documented in [spatial layers and uncertainty](docs/spatial-and-uncertainty.md). Automatic semantic segmentation and validated pixel-level chemical retrieval are not implemented.
