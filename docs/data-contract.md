# Dashboard data contract and execution plan

## Serving architecture

Vercel serves the React/Vite frontend. FastAPI serves indexed, paginated records. PostgreSQL is the production source of truth; local development uses SQLite. A separate Python worker claims database jobs and runs frozen CPU-capable models. Heavy inference never runs in the HTTP request or the Vercel frontend.

The first registry contains the actual validation-selected models: histogram gradient boosting over RGB plus metadata for chlorophyll-a, and a small CNN plus metadata for Kd(490). Both predict log10 concentrations internally; the worker converts to positive physical values. The original experiment files remain untouched.

The database has six tables: `photos`, `satellite_matchups`, `model_versions`, `prediction_runs`, `estimates`, and `jobs`. Estimates are unique by run, photo and model. Each estimate references the exact matchup, so a later satellite extraction cannot silently change an older comparison. Model identity is a hash of checkpoint/preprocessor/source hashes and the selected candidate. Run provenance records source-export hashes and cohort rules. Worker outputs record decoded-image hash and the exact transformed metadata inputs.

Photos are canonical and imports do not mutate their metadata. A future metadata-correction workflow should add explicit photo revisions and input snapshots, including who corrected the record. Model artifact versions must be archived before replacing local files; the worker rejects files whose hashes differ from the registry. Archive and restore the exact registered source/checkpoints to rerun an older version.

## Which data powers each card

| Dashboard field | Source / computation | Current availability |
|---|---|---|
| Image ID, mission, URLs | NASA ID + frozen manifest | Available |
| Capture time, coordinates, sun, cloud, focal length | Catalog metadata in frozen manifest | Nullable; unknown remains unknown |
| Chlorophyll-a (mg/m³) | Frozen selected regression model | Available |
| Kd(490) (m⁻¹) | Frozen selected CNN | Available |
| Satellite concentration | Positive finite, quality-masked L2 pixels; geometric mean | Available for imported benchmark |
| Satellite time/coverage | Exact granule ID, absolute time gap, footprint overlap | Available |
| Pixel retention | Per-target valid counts/fractions + named excluded flags | Available |
| Prediction minus reference | Same target, units and estimate-linked matchup | Available; not a confidence measure |
| Prediction interval | Exact model version and independent scene-group calibration | Pipeline available; current benchmark has no eligible calibration |
| Water clarity class | Needs documented physical definition and validation | Unavailable |
| Ocean/coastal type & semantic indicators | Requires catalog/reviewer labels or a versioned classifier | Not integrated; earlier classification pipeline can be a separate future table |
| Spatial layers | Source-bound raster or reviewed normalized polygons | Experimental heatmaps and manual annotations; no automated validated segmentation |
| Usefulness score | Needs a versioned rubric and validation against reviewer decisions | Unavailable |
| Camera, orbit, geographic place name | Additional NASA metadata joins | Not present in imported manifest |
| Collection | Browser storage, exportable ID list | Local to browser; no team/account synchronization |

## Execution stages

1. **Catalog:** validate IDs, UTC times, coordinates and image decoding; store image hash and immutable source metadata. Retain missing values and known eligibility failures.
2. **Feature extraction:** use the same RGB crop, normalization, metadata feature order and preprocessing as training. Satellite values, valid fractions and matchup time gaps are never inference features.
3. **Inference:** pin model versions; write a durable job before returning HTTP 202. Claim atomically, compute away from HTTP, and commit all requested target outputs plus completion in one transaction. Partial output is never presented as complete.
4. **Satellite matchup:** independent of inference. Existing verified matchup imports are supported. A future extraction job must store granule version, selection rule, footprint geometry, mask version, counts/fractions, units and aggregation; it must preserve failed/no-match records too. Do not substitute an unrelated nearby granule.
5. **Serve:** list queries use bounded pages and stable sorting. Photo detail chooses the most recent completed output per target and returns its model, run and matchup IDs. `/history` exposes previous outputs. Different targets can originate from different runs and carry their own provenance.
6. **Evaluate:** retain scene-group and split membership. Never relabel a training photo as unseen by rerunning it. Use a new geographic/site-disjoint benchmark and in-situ observations before claiming operational generalization.

## Storage decisions

Use PostgreSQL for searchable metadata, model/run manifests, estimates, labels and job status. NASA remains the public imagery origin. The local API can serve the already-cached image files; otherwise it redirects to NASA thumbnails. Keep checkpoints, immutable source exports and future NPZ/GeoTIFF masks in a versioned private object store, indexed by hashes and manifest IDs, rather than database blobs. The current implementation reads these artifacts from the trusted NASA filesystem; object-store adapters and scheduled catalog/satellite ingestion are next-stage work.

The current cohort is 1,501 training photos, 279 validation photos and 350 test photos. It is a screened subset, not the full archive, and its holdout comes from an image pool used in previous experiments. The exploratory spatial maps in the workspace must remain labeled exploratory if they are added later.

## API

`GET /api/summary`, `/photos`, `/photos/{id}`, `/photos/{id}/thumbnail`, `/photos/{id}/history`, `/models`, `/runs`, `/jobs`, `/jobs/{id}` and `/health` are read-only. `/photos` supports `q`, `mission`, `split`, `start`, `end`, `prediction`, `satellite`, `south`, `north`, `west`, `east`, `sort`, `offset`, `limit`. Bounding boxes may cross the antimeridian.

`POST /api/jobs` requires operator bearer authentication and an `Idempotency-Key` header. Body: `{ "photo_id": "ISS005-E-11615", "model_ids": ["registered-version-id"] }`. Reusing a key with different inputs returns 409. Requests can only select existing catalog photos and registered models; callers cannot supply arbitrary URLs, filesystem paths, code or checkpoints. The CLI is the trusted ingress for new local photos.

## Spatial and uncertainty additions (schema v2)

`overlays` stores immutable source-bound experimental raster artifacts, a separate spatial model fingerprint, units/scales, source preview and compressed pixel grids. `annotation_revisions` stores append-only snapshots of normalized polygons, reviewer attribution and source hash with a unique photo/revision pair. `calibrations` stores exact scalar-model linkage, scene-group conformal radius, nominal coverage, full reviewed cohort/reference provenance and method version. No old estimate rows change. Photo responses now include a structured `prediction_interval` (bounds and calibration ID, or an explicit unavailable reason). `confidence` remains null. See `spatial-and-uncertainty.md` for API and scientific semantics.
