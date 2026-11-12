# Dashboard regional RGB model — 3 November 2026

The map-first viewer now uses a **new model trained on regional labels**, in
`../appa_spatial_20261103/`. It is separate from the earlier scalar ConvNeXt
models and their occlusion diagnostics. The default model-map filter shows 11
supported sample photos, including two without satellite references, with 289
assessed water regions. Predictions are actual model outputs from the registered
RGB crop plus supported metadata. No current-photo satellite values enter inference.
The first static artifact set is about 87 KB; no map bytes or new tables were
added to Supabase. Whole-crop diagnostics and satellite comparisons are collapsed
below the map and retain their original model identities.

## Input, masking and labels

The source is the existing Mediterranean manifest and local MODIS subsets.
Only EarthMatch-verified photos with at least 100 inliers, cloud fraction <=3%,
hardware <=1%, and footprint <=40,000 km² qualify. At most 24 deterministic
photos per source group are selected. Regions use an 8×8 grid on the exact
registered crop, with every side at least 5 km. Entire regions touching land or
a 2-km coastal buffer are excluded using GSHHG and the recorded geometry.

A prediction-blind nine-photo audit caught cloud contamination in the first
screen. Before fitting, it was tightened to require >=98% usable pixels
(maximum RGB channel .05–.65, saturation >.25), at least 128 usable pixels, and
95th-percentile brightness minus median <=.10. This is a conservative heuristic,
**not validated cloud/glint segmentation**. The before/after audit images and
initial protocol are retained. Independent registration RMSE remains unknown.

Labels are geometric means of jointly quality-passing chlorophyll/Kd pixels
inside each region, requiring >=5 satellite centers and >=75% good coverage.
References must change by <=25% under each of four 2-km shifts. This restricts
the evaluation to supported, spatially stable references; that stability cannot
be checked when a new photo has no satellite data. Map and confidence transfer
therefore assume comparable inputs. Grid cells are approximate geographic
sampling regions, not precise satellite pixel footprints.

## Training and evaluation

20,594 labeled regions survive across 890 photos. Source-linked scene,
timelapse, granule and decoded-pixel groups cannot cross splits. Eight hashed
training groups were reserved for calibration before fitting.

| Split | Photos | Regions | Scene groups |
| --- | ---: | ---: | ---: |
| Train | 437 | 10,262 | 27 |
| Validation | 58 | 1,178 | 7 |
| Calibration | 143 | 3,590 | 8 |
| Test | 252 | 5,564 | 15 |

Each target has a whole-water level head and a regional residual head. RGB
features include channel quantiles/means/spreads, chromatic fractions and log
channel ratios. The regional head receives the region's color difference from
the photo's usable-water context plus that context. The global head receives
water RGB context and nine location/time/solar/cloud fields. Context is computed
from **all input-eligible regions**, not just regions with satellite labels, in
both training and serving. Ridge and histogram-gradient-boosting candidates were
specified before scoring. Both targets selected global ridge alpha=10 and
regional ridge alpha=1000 on validation only. Both selections were saved before
test scoring. Equal weight per scene is used for evaluation.

| Held-out result | Chlorophyll-a | Kd(490) |
| --- | ---: | ---: |
| Regional log10 MAE | 0.17345 | 0.10994 |
| Flat-control log10 MAE | 0.19173 | 0.11879 |
| Within-photo contrast error reduction | 19.27% | 14.20% |
| Regions within ±25%, scene weighted | 39.94% | 59.72% |
| Scene groups with improved contrast | 8/15 | 8/15 |
| 95% scene-bootstrap contrast improvement | −6.58% to 36.69% | −11.26% to 30.04% |

The preset exploratory map gates passed (>=10% mean contrast improvement,
absolute MAE no more than 5% worse than flat, >=8 test groups). **Bootstrap ranges
include no improvement**, so consistent benefit on new scenes is not established.
This remains an experimental Mediterranean model, not validated dense retrieval
or a geographic extrapolation benchmark. The existing source test scenes had
previously been inspected in scalar experiments; this is retrospective research.

## Regional confidence and serving

Regional confidence uses a separate score fit on validation errors, a sigmoid
calibrator fitted on the reserved calibration groups, and evaluation on the 15
test groups. The event is absolute relative error <=25% against the regional
satellite reference. Whole-crop confidence is never copied onto a region.
The new chlorophyll calibrator failed (ECE .218, Brier .311 versus constant .253)
and is not displayed. Kd passed overall (ECE .079, Brier .247 versus constant
.267); only its 40–60% probability band passed the per-band checks. Rounded
percentages are shown on 192 of the 289 exported Kd regions. No percentage is
invented for other regions.

`photo_regions()` and `model.predict()` form the shared inference path.
`export_dashboard.py` reads only the bounded 100-photo sample and writes hashed
JSON assets under `public/spatial-maps/`, with input/model/protocol provenance.
`verify_release.py` removes all satellite target, identity and QC columns and
replays **all 11 maps**, including the two reference-free photos, to relative
tolerance 1e-12. Confidence values and region boxes also match exactly. Five
scientific controls check land exclusion despite water-colored RGB, dark/bright
rejection, invalid-input failure, spatial error versus constant bias, and reference
axes/quality-flag separation from the inference mask.
The frontend production build and local region selection/target switching pass.
All 11 public static artifacts match the tested bytes. Three live API crop checks,
including both reference-free photos (ISS065-E-120265 and ISS073-E-470968), pass.
The public viewer was checked on ISS067-E-127704 (17 offshore regions) and an
unsupported orbital-estimate photo, which correctly has no colored map.
Final production deployment: `dpl_3HrSLHM612SHjnwLqyj9LJMkRCFb`.

The viewer defaults to a clearly labeled per-photo color scale to expose regional
variation; a common scale is also available. Numerical ranges and units remain
visible. Blank areas mean unassessed, not zero. The highest displayed value is
an estimate, not a confirmed bloom or a significance claim.

To reproduce with the existing scientific environment, run `prepare.py`,
`train.py`, `calibrate.py`, `evaluate_uncertainty.py`, `export_dashboard.py`, and
`verify_release.py` from the model folder using
`../kd490_proposal/.venv/bin/python`, with `OPENBLAS_NUM_THREADS=2` and
`OMP_NUM_THREADS=2`. Frozen protocol files guard changes; create a new model
version rather than retuning against this inspected test set.

---

# Earlier scalar-model regional diagnostic — 3 November 2026

At this earlier stage, the live Mediterranean models emitted whole-crop scalars. Satellite layers are
measurements from MODIS, and occlusion layers measure changes in a scalar after
hiding image regions. Neither is a local model prediction. The interim viewer started
with the photo, shows both targets' confidence statuses together, and puts
satellite percentage differences in a separate optional comparison. Available
Kd confidence applies only to the whole-crop output. The failed chlorophyll
confidence candidate remains unpublished. See `confidence-release-2026-11-03.md`
for the current percentage protocol; the older interval documentation below is
a separate workflow.

`scripts/check-regional-inference.py` tested the current exact checkpoints on
16 non-overlapping, enlarged tiles from each of the 18 pilot inputs. The original
whole-photo metadata was fixed. Input and checkpoint hashes were verified and
the unmodified whole-crop prediction replayed within 2e-4 log10 units before
the tile pass. Satellite values were excluded from inference. No confidence
scores were assigned to tiles. No maps were written to the database or published.

The evaluation reused the existing approximately projected satellite display
grids. A region needed at least four valid display samples and 75% coverage;
a photo needed at least four such regions. Ten of the 15 matched photos qualified
for both targets. The three unmatched photos also ran successfully but could
not be scored. Display samples are correlated, the photographs are not necessarily
independent scenes, and this previously inspected pilot is **not independent
spatial validation**. Equal weight was given to each scored photograph.

| Diagnostic | Chlorophyll-a | Kd(490) |
| --- | ---: | ---: |
| Regional log10 MAE | 0.21137 | 0.09008 |
| Whole-crop flat control log10 MAE | 0.15772 | 0.09637 |
| Within-photo contrast MAE | 0.07632 | 0.04877 |
| Flat contrast MAE | 0.07685 | 0.04732 |
| Contrast skill versus flat | 0.68% | −3.07% |

Contrast removes each photo's mean from both prediction and reference, so a
better overall level cannot masquerade as better localization. These results
do not demonstrate useful localization. Enlarging scalar-model crops also changes
scale and context from training, and no semantic water mask exists. The shortcut
is therefore retained as a local diagnostic, not offered as a concentration map.
Raw values, boxes, hashes and per-photo results are in
`runtime/regional-inference-diagnostic.json`; three scientific-control tests in
`scripts/test-regional-inference.py` pass (perfect/biased pattern, flat control,
missing coverage). The frontend production build passes. Public UI checks confirm
80% Kd confidence on unmatched ISS042-E-104322, 60% on matched ISS031-E-50002,
photo default, optional sensitivity, and explicitly labeled satellite comparisons.
Deployment: `dpl_HPhnGiLDNPTKq3s2D4ZRzeif7dAN`.

## Work needed for the requested model map

1. Acquire actual photo water/cloud/glint masks and verify their coordinates
   against the registered model crop. A photo-level water fraction is insufficient.
2. Check photo-to-satellite registration using independent control points; reject
   failed scenes and select a coarse map resolution supported by measured error.
   Four supplied corners are not independent registration validation.
3. Build region-level training labels from quality-screened, aligned satellite
   pixels. Freeze independent scene/geographic/granule groups **before tiling**.
4. Train a regional predictor on those regional labels. At inference it receives
   only the photograph and supported metadata/masks, with no satellite target
   values. Benchmark a coarse patch model before investing in a dense decoder.
5. Evaluate both absolute values and within-photo spatial contrast against a
   flat whole-photo control on new held-out scenes. Include alignment sensitivity,
   missing coverage, cloud/glint and new-region checks. Calibrate regional
   confidence separately using further reserved groups.
6. Release bounded versioned map artifacts as static files/object storage, with
   clickable region values, common concentration scales and transparent unsupported
   areas. Keep map bytes out of the free Postgres database. Satellite layers stay
   optional comparison layers; whole-photo confidence is never copied onto tiles.

The older Sammy coarse-grid experiment did show preliminary contrast skill on
three test photos, but severe per-scene errors, provisional alignment and the
different image domain prevent treating it as a validated Mediterranean map model.

---

# Legacy experimental spatial layers and prediction intervals

## What is available

The image viewer offers Original, Chlorophyll-a, and Kd(490), a fixed logarithmic legend, opacity, pixel inspection, and a JSON export. Maps are generated from the existing `RGB_transformed_ridge_100` pixel experiment, **not** the selected scalar models. They were trained against photo-level satellite aggregates, not spatial labels. Land, cloud, glint, color balance, and camera processing can therefore influence the maps. The technical dark/saturated exclusion is not a water mask. There is no georeferencing, pixel-level validation, or semantic detection confidence.

Reviewed regions are normalized polygons with explicit classes: water, land, cloud, coast, plume, glint, possible bloom, unknown. Click Draw region, place at least three points, and Finish polygon. A region can be removed and redrawn; class toggles control visibility. Browser drafts survive switching photos. Save review requires the configured operator key and a reviewer name; exports do not. Every database save appends a complete revision, including removals, without replacing earlier reviews. Revision conflicts return 409. Coordinates must be finite, within the image, and form non-crossing polygons with area. Multiple regions may overlap. Names are operator-supplied attribution, not individual authenticated identities. Region classes are reviewer annotations, not automated detections or chemical confirmation. No automatic SAM detector has been integrated.

The local key is in the ignored `.env` file as `OPERATOR_API_KEY`. Never add it to a frontend environment variable, commit it, or paste it into public channels. The browser holds it only while the save dialog is open.

## Generate and serve layers

Run from the dashboard root, using the existing scientific environment:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=runtime/matplotlib PYTHONPATH=backend \
  ../kd490_proposal/.venv/bin/python -m app.overlays
```

Use `--photo-id ISS005-E-11615` (repeatable) or `--limit 30` for a subset. Generation is idempotent by photo, source hash, target and spatial model fingerprint. Changed code/checkpoints create new versions; previous layers remain readable. The CLI reports failures and can be rerun after correcting them. Scalar inference workers now also generate spatial layers after successful inference, recording `overlay_status` in run provenance. If a worker stops between scalar completion and spatial generation, rerun `app.overlays` to backfill. A spatial failure does not discard valid scalar predictions.

Each layer stores a SHA-256 of the decoded RGB source, source/map dimensions, checkpoint/code/training-manifest hashes, fixed training-label display limits, experimental status, a matching source preview, transparent PNG, and losslessly compressed JSON grid (log10 values rounded to five decimals, excluded pixels null). Layers use the entire frame at a maximum side of 256 pixels. This preserves aspect ratio and exact alignment between the source preview and map; it does not add spatial detail to the model. API decoding uses the standard library; the API host does not load ML dependencies. The worker needs the existing scientific Python environment including matplotlib.

`GET /api/photos/{id}/overlays` returns metadata, current image hash, and latest annotations. `GET /api/overlays/{id}/image.png`, `/source.png`, and `/values` return immutable artifacts. The viewer uses the latest layer per target. `GET /api/photos/{id}/annotations` exposes the latest 100 revisions; all remain stored. `POST` to that path appends an authenticated review with a client revision ID, base revision, image hash, reviewer, and regions. Repeating identical content with the same ID is idempotent.

## Calibration workflow

No calibrated numerical intervals have been assigned to the current benchmark. All its train, validation and test scenes are already exposed. Aggregate test error factors are not per-photo confidence scores.

The implemented workflow uses absolute log10 residuals, the **maximum residual per scene group**, and the finite-sample split-conformal order statistic `ceil((G+1)*coverage)`. The interval is `prediction × [10^-q, 10^q]`. Each group counts once, regardless of how many neighboring frames it contains. Under exchangeability of calibration and future scene groups, this targets nominal scene-group marginal coverage. It is not conditional/per-photo accuracy, an observed coverage result, an in-situ measurement interval, or segmentation confidence. Separate calibrations are required for each exact scalar model version. Choices of coverage, cohort, domain and grouping must be frozen before inspecting calibration residuals.

1. Assemble **new** scenes, excluded from all prior training, selection, inspection and calibration. Assign connected groups accounting for image sequences, nearby captures, duplicate pixels and shared satellite granules; review against earlier research pools as well as this dashboard. Supply `scene_group`, `calibration_domain`, and a written `independence_review` in the catalog CSV. The importer stores these fields without changing existing photos.
2. Run the frozen scalar models on these photos. Export their estimate IDs from `/api/photos/{id}/history`. Generate quality-masked satellite geometric means using the same target definitions and eligibility rules as the benchmark. Retain reference source, granule ID and dataset SHA-256. This release does not fetch or build new satellite matchups.
3. Create a cohort JSON from `docs/calibration-cohort.example.json`. Include at least 20 independent groups; higher nominal coverage may require more for a finite interval. Twenty is a software minimum, not a scientific sample-size recommendation. The written reviews are operator assertions; software cannot establish geographic independence from prose.
4. Run `PYTHONPATH=backend .venv/bin/python -m app.calibration cohort.json`. It rejects exposed estimates, model mismatches, repeated IDs or decoded pixels, known scene groups/granules, unreviewed domain assignments, and shared granules split into different groups. The transaction records the cohort, references, residual scores, algorithm hash and calibration version together.
5. Ingest and predict separate future photos with matching reviewed domain metadata and independent groups. The read API automatically supplies `prediction_interval` with bounds, nominal coverage, calibration ID, group count and limitations. It suppresses intervals on benchmark and calibration scenes, duplicate inputs, missing review, and unmatched domains. It retains `confidence: null`; no arbitrary percentage appears. The interval is reproducible from the immutable estimate and calibration version returned in the API/export.
6. Evaluate empirical coverage and width on a further, independent evaluation cohort before making performance claims. Coverage evaluation is **not yet automated**; all calibration records explicitly say independent coverage evaluation is pending. Assess new cameras, geographic regions and acquisition conditions separately for distribution shift.

The example file is a schema template with placeholders, deliberately not a runnable scientific cohort. Unit tests use synthetic data only in isolated temporary databases. There are no synthetic calibrations in the dashboard database.

## Deployment and storage

For an existing PostgreSQL database, apply `backend/schema-v2.sql` after v1. This additive transaction creates overlays, annotation revisions and calibrations in private schema `appa`. Local initialization adds the same tables. No original scientific files or existing estimate rows are rewritten.

Compressed artifacts currently live in the SQL database, so a Vercel API can serve them without the worker filesystem or an additional storage credential. Budget disk/database size for the full catalog and retained versions; it can exceed a small free database quota. For larger deployments, move binary/grid payloads to private object storage (for example Supabase Storage), retaining their hashes and locators in SQL; that adapter is not implemented. Back up SQLite with the SQLite backup API (not a raw copy while writers run). A production Supabase/Vercel connection remains a separate deployment prerequisite.
