# Latest pixel-overlay deployment — 12 November 2026

The dashboard now opens the latest published native-pixel catalog (2,275 ready photos). Cohort and prediction-run selectors have been removed. Filtering uses mean absolute percentage error over matching satellite regions; the tutorial covers the error filter, results, comparison, and export.

Production requires `VITE_NATIVE_CATALOG_BASE` pointing at the directory containing `index.json` and `run.json`. The local `/native-scaleup` middleware is development-only. **Do not promote the frontend until every object in the latest catalog is hosted and verified.** A frontend-only release would have no latest results.

The complete native overlay assets occupy approximately 9.24 GB, plus small metadata files. They belong in object storage, not Postgres or this Git repository. The current Supabase Free storage allowance cannot hold this release. On 12 November the user requested preparation of a Pro upgrade; no subscription change has been made yet. The organization has two active projects, so review the full billing estimate before accepting.

Use a versioned object-storage prefix, preserve exact bytes and checksums, verify each published detail and raster, and publish the catalog index last. The browser downloads individual photo details and rasters on demand; filtering reads compact index metadata. Keep upload concurrency and retries bounded. Public NASA imagery and derived model outputs may be served from a public-read bucket; write access remains server-side. Do not expose service credentials in frontend variables.

Frontend project: `astronautphotographypredictionanalysis`. API project: `appa-api`. Keep the existing same-origin API rewrite. The API changes add NASA metadata enrichment and geographic filters; there is no schema migration or bulk database import for this release.

Checks: 37 backend tests passed, one frozen-model replay skipped in the lightweight environment; frontend assertions and Vite production build passed. Browser verification covered the error filter, exact filtered export, first-visit/restarted tutorial, highlight cleanup, and desktop/mobile layout.

Prepared upload manifest: **11,377 objects, 9,259,170,970 bytes**, covering all 2,275 photos. Generate a fresh private manifest with:

```sh
python3 scripts/prepare-native-release.py \
  --source ../high_density_pixel_scaleup_20261112 \
  --output runtime/cloud-native-20261112-v1 \
  --base-url https://qcjkgrelvnivgpfwrfan.supabase.co/storage/v1/object/public/appa-overlays/native-20261112-v1
```

The script rewrites only release metadata, recalculates detail hashes, and preserves all numerical raster bytes. The private upload manifest contains local paths and must never be uploaded. Store only the listed objects at the versioned prefix. The reviewed Pro checkout quotes **$25 today and $35/month estimated** with two active projects; final approval is pending. Keep the existing spend cap enabled.

The sections below describe the earlier 100-photo cloud sample and infrastructure history; they are not the current catalog deployment instructions.

---

# Deployment plan

## Recommended initial production arrangement

The frontend uses the existing Vercel project and the lightweight FastAPI API uses `appa-api`. The user authorized **APPA Sample**, project `qcjkgrelvnivgpfwrfan`, in **moxiefoxie's Org**, **Free plan only**, on 3 November 2026. Johann's **Geolocation** project `zwdkkwbxlsrlqsqjfdht` is a separate read-only source. The previous review project is preserved after its failed oversized import. No billing changes are authorized.

This release imports only a deterministic 100-photo demonstration sample from the verified local exports. Saved Mediterranean predictions work; new inference is disabled until compatible ConvNeXt adapters and a supervised worker are available. See [sample release status](sample-release-2026-11-03.md).

FastAPI's [background-task guidance](https://fastapi.tiangolo.com/tutorial/background-tasks/) distinguishes request-followup work from heavy computation; this project uses a durable external worker. SQLAlchemy supports both [SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html) for local operation and PostgreSQL for deployment.

## Database

Set the same `DATABASE_URL` for the API, importer and worker. PostgreSQL queries explicitly target private schema **appa**, keeping this application separate from the older review portal. Do not expose `appa` through Supabase's Data API or grant browser/anonymous roles access. The frontend never receives database credentials or a Supabase service-role key.

`backend/schema-bootstrap.sql` is the current fresh-install DDL; `schema-indexes.sql` adds the latest foreign-key indexes. Use `schema-v3.sql` only to upgrade an existing v2 installation. `create_all` does not upgrade existing tables. The hosted project uses a separate `appa_runtime` login with access only to the private APPA tables. Vercel disables automatic schema creation. Enable provider backups and perform a restore drill before treating the database as the only copy.

The earlier review project exhausted disk during a failed 1.07 GB legacy-overlay transfer. The new sample importer excludes overlays and image bytes, caps the sample at 100 photos and 2 MiB, verifies destination identity and database headroom, and commits ten-row batches with a one-second delay. Conflicting existing records stop the import. Physical disk headroom was checked separately before the new import.

## API on Vercel

Create a second Vercel project using this same Git repository, with **Root Directory `backend`**, framework **FastAPI**, and Python 3.12. `backend/vercel.json` and `.python-version` provide the entrypoint settings. The existing frontend project keeps the repository root and Vite preset. The API runs at `https://appa-api.vercel.app`; root `vercel.json` proxies `/api` to it. Leave `VITE_API_BASE_URL` unset for this same-origin setup.

[Vercel supports FastAPI](https://vercel.com/docs/frameworks/backend/fastapi) directly, and its [Python runtime documentation](https://vercel.com/docs/functions/runtimes/python) specifies the supported entrypoints and versions. The API and frontend are deployed separately. Verify the live health, sample counts and detail endpoints after each deployment.

Use the **Supabase transaction pooler URI** in `DATABASE_URL` for the API. Copy the exact host/user/port from the project's Connect panel and securely substitute the database password. The existing Supabase HTTP service key is not a PostgreSQL password. Server-side SQL uses explicitly qualified schema names, disables Psycopg automatic prepared statements for [Supabase transaction-pool compatibility](https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL), sets `extra_float_digits=3` within each transaction to preserve exact [floating-point round trips](https://www.postgresql.org/docs/18/datatype-numeric.html), and uses `NullPool` to avoid stacking a long-lived application pool on the managed pooler. A session-pool URI may be used by the local long-running worker; it must address the same database.

Set `DB_AUTO_CREATE=0` on Vercel and apply migrations before deployment. The API fails closed if deployed to Vercel without PostgreSQL; it cannot silently use ephemeral SQLite. No Torch/model checkpoints go into this API project.

### Optional container hosting

A container definition is also supplied if you prefer a long-lived API host:

```sh
docker build -f backend/Dockerfile -t appa-api .
docker run --env-file /secure/path/api.env -p 8000:8000 appa-api
```

Required production environment:

- `DATABASE_URL`: private PostgreSQL connection string; use TLS (`sslmode=require`).
- `OPERATOR_API_KEY`: a long random secret for inference submission; leave unset to disable writes.
- `INFERENCE_ENABLED=0`: keep queue submission disabled until a supervised compatible worker is running.
- `ALLOWED_ORIGINS`: comma-separated exact frontend origins, including `https://astronautphotographypredictionanaly.vercel.app`.
- `NASA_WORKSPACE`: only necessary on the API host if it serves cached thumbnails. Otherwise thumbnails redirect to NASA.

Put the service behind the host's HTTPS endpoint and configure health checks at `/api/health`. Keep database network access limited to the API/worker and operator environment. Rate-limit operator job submissions at the host/proxy. The shared operator key is suitable for a controlled capstone demonstration; per-user Supabase/JWT authentication, role checks, audit identity and quotas should precede broader multi-user submissions.

## Import and worker

For the first deployment, the local NASA machine can act as the supervised worker and importer, connecting to remote PostgreSQL while retaining the existing trusted ML environment and data. It must remain awake/running. For unattended service, move the artifact bundle to persistent storage on a worker host and configure `NASA_WORKSPACE` there. Do not bake source photos or model weights into the public Vercel build.

Required files include the frozen manifest/prediction/summary/audit exports, feature schema, selected model bundles, CNN checkpoint and metadata preprocessor, `deep_models.py`, `prepare.py`, and the RGB feature extraction source under `quick_chl_kd_baseline`. All manifest-referenced photos must be accessible. The current benchmark CSV contains original absolute paths: when moving to a new host, preserve/mount those paths or explicitly remap the private `photos.local_image` locators during migration. Validate decoded hashes before accepting the move. Run the parity test again after migration; never edit the frozen scientific exports merely to make a path work.

Verify the local imports with `python -m app.verify_mediterranean`, then use `python -m app.transfer --apply` with the destination configured to copy the core records in resumable batches. Large overlays stay local until object storage is configured. The user now authorizes only a sample; `app.transfer` defaults to 100 photos with a 2 MiB payload ceiling and ten-row paced batches. It no longer transfers the full catalog. See `sample-release-2026-11-03.md`. Verify again against PostgreSQL before switching the API. The API container alone does not run inference. Importer and worker CLI commands need `PYTHONPATH=backend` from this checkout, or an equivalent installed module path.

The local API package pins are recorded in `backend/requirements.txt`; model serving should preserve the existing ML runtime versions in `backend/worker-runtime-versions.json`. Do not load third-party pickle/joblib checkpoints.

## Vercel

The frontend uses the same-origin `/api` rewrite in root `vercel.json`; leave `VITE_API_BASE_URL` unset. Use the existing project's Vite build: `npm ci`, `npm run build`, output `dist`. No secret belongs in a `VITE_` variable. The dev proxy in `vite.config.js` is only for localhost.

Before switching the live site: verify HTTPS, database restore, exact-origin CORS, unauthorized POST rejection, repeat-key deduplication, import counts, real checkpoint completion, job recovery after a worker restart, pagination and the visible training/test labels. Publishing the frontend before the API exists would produce a connection error, so deploy the services first.

## Remaining work beyond this release

Automated new satellite extraction, object-store artifact adapters, automatic validated segmentation, metadata enrichment, team collections, browser uploads, scheduled refresh and broader user authentication are not implemented. Experimental heatmaps, reviewed polygons and calibration tooling are implemented; numerical intervals still require fresh independent calibration data. They are separate data/model features, not fields that can be filled from existing regression outputs.

### Spatial artifacts

Do not backfill large overlays into the Free sample database. The legacy experimental layers remain local. A future cloud release needs object storage, artifact compatibility checks and explicit capacity planning. See [spatial and uncertainty operations](spatial-and-uncertainty.md).
