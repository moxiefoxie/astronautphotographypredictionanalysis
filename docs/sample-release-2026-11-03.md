# Free sample release — 3 November 2026

The user explicitly authorized a new **APPA Sample** project in **moxiefoxie's Org**, **Free plan only**, and limited the import to a sample. No billing changes or old-project deletion were performed.

- Database: `qcjkgrelvnivgpfwrfan`, us-east-1, [Supabase dashboard](https://supabase.com/dashboard/project/qcjkgrelvnivgpfwrfan).
- Frontend: [APPA dashboard](https://astronautphotographypredictionanaly.vercel.app).
- API: [health](https://appa-api.vercel.app/api/health), [documentation](https://appa-api.vercel.app/api/docs).
- The local dashboard also connects to this sample database. The frontend now hosts 100 compressed previews of the registered model-input crops, verified against the frozen source hashes. They are static Vercel assets, not database rows. The API retains its NASA-original fallback for clients without the packaged previews.

## Imported sample

100 Mediterranean photos: 50 with usable satellite references and 50 inference-only. The database contains 200 unchanged saved predictions, two exact model versions, 50 matchups, 100 versioned catalog snapshots, 100 input-asset records and one sample run.

Selection is deterministic by SHA-256 rank within reference-availability groups. This is a balanced demonstration sample, not a representative accuracy study. Original model evaluation metrics remain labeled separately. Sample run and estimate IDs preserve source lineage. Johann's project remains read-only; these are saved exports, not a live feed.

Serialized payload: **975,774 bytes**. Total database size after verification: **13,006,515 bytes**. Before import, SQL worked, read-only mode was off, and the Supabase dashboard reported 13% physical disk usage. No overlays, image bytes, model binaries, jobs, annotations or calibrations were copied.

## Verification

- Every row in all seven imported tables matches its local source exactly, including prediction values, input hashes, references and provenance.
- Confirmed zero rows in all excluded application tables and no anonymous access to the private `appa` schema.
- The scoped runtime role is `appa_runtime`; database credentials stay server-side.
- Live API checks passed for health, counts, both satellite-reference cases, empty legacy cohort, models/runs, pagination and disabled unauthenticated mutations.
- PostgreSQL pooler sessions returned rounded floats with `extra_float_digits=0`. The client now sets `extra_float_digits=3` within every transaction; exact round-trip checks and deployed API values pass. No stored prediction needed rewriting. See [PostgreSQL numeric output documentation](https://www.postgresql.org/docs/18/datatype-numeric.html).
- Backend suite: 26 passed, one optional ML test skipped in the lightweight API environment. The frozen model replay had separately passed earlier (18 outputs across nine photos).
- Frontend production build passed. Its roughly 503 kB JS bundle triggers a non-blocking size advisory.
- Published browser verification passed: Supabase connected, 100/200/1 totals, sample notice, real estimates and references, labeled NASA preview fallback, disabled inference controls, and one completed 100-photo run. Screenshot: `runtime/appa-sample-live.png`.
- Idle run-history polling is disabled; active submitted jobs alone trigger polling.
- Production deployments: API `dpl_GyJoV4q1nVK4zP74xNVdrPNcHhWX`; frontend `dpl_BRr728G3BUvUQb57N5QcR9THKUMG`.

Local ignored verification artifacts: `runtime/sample-import.json`, `runtime/cloud-sample-verification.json`, `runtime/sample-preflight.json`.

## Operating limits

`app.transfer` permits 2–100 photos and at most 2 MiB of serialized records, targets only this project, checks database size, and uses ten-row transactions with a one-second pause between changed batches. Existing conflicts stop the import; matching records are skipped. Physical disk/WAL headroom must also be checked before a future import. Do not run a full catalog or overlay transfer.

```sh
# Local-only preflight; does not connect to Supabase
PYTHONPATH=backend .venv/bin/python -m app.transfer
```

New model inference and operator writes are disabled on the public deployment. Compatible ConvNeXt adapters, calibrated uncertainty, validated segmentation and continuous source synchronization remain future work. Unsupported confidence/usefulness scores and bloom/clarity claims are omitted; see [feature decisions](feature-decisions.md).

## Preserved old project

The old `astronaut-photography-review` project (`yppshbgdkyozwrsnbshy`) remains intact. Its disk-full incident and support ticket **SU-535994** are separate from the new sample release. The AI support reply documented an upgrade-based recovery path; none was taken. The earlier disk-I/O email warned about exhausted burst I/O, not successful recovery. See the [historical incident record](release-status-2026-11-02.md).

## Safari image-delivery fix

A user reported blank thumbnails and a collapsed photo area on the public site in Safari. The former image endpoint redirected browsers to NASA; it worked in the test browser but remained unreliable for the user. The frontend now serves the same 100 sampled crops directly from its own origin. All source hashes were verified before JPEG encoding; these are compressed display copies and never replace model inputs. The manifest checks the exact input-asset ID and source hash before using a preview for a prediction. The main viewer now reserves space and shows loading/error/retry states.

The 100 preview files total 13,275,405 bytes on Vercel. No Supabase image storage, database writes, billing changes, or additional source-photo imports were needed. Main viewer, thumbnails, comparisons and collections share the packaged paths. `scripts/build-sample-previews.py` reproduces the assets from the local frozen sample.

Production fix deployment: `dpl_7zzYQdrebA6odDvV5RhvnyxfAbvL`. All 100 preview URLs returned HTTP 200 with `image/jpeg` and no redirects. The main photograph and thumbnails were visually verified in the user’s Safari tab after refreshing.

## Fifteen-photo evidence pilot

The default view now selects 15 EarthMatch-verified sample photos with usable satellite references. Photographs are capped at 340 px tall. Each target has a clickable 4×4 occlusion-sensitivity layer, an approximate satellite-reference layer, a photo-only view, an opacity control, and an evidence export. All 100 photos remain available through All photos.

`scripts/build-evidence-pilot.py` reads local frozen inputs and checkpoints without training or cloud writes. It verifies input/checkpoint/granule hashes, reproduces training metadata and partial-model float16 cache behavior, and replays all 30 predictions before evaluating 480 regional occlusions. The maximum replay difference is 3.4571e-6 log10 units. All 30 satellite valid-pixel counts and geometric means match the stored references. The 15 content-addressed JSON artifacts total 321,946 bytes, served by Vercel; no Supabase storage or billing changes occur.

Sensitivity replaces each tile of the exact preprocessed input with that image’s mean RGB while holding metadata fixed. The selected region reports the actual prediction change. Colors and their relative intensity describe this perturbation experiment, not concentrations, causal attribution, uncertainty, or bloom detection. See the [occlusion method](https://captum.ai/api/occlusion.html) for the method family. Existing saved model outputs remain unchanged.

Satellite layers use a 32×32 display grid sampled from nearest native pixels, preserving quality-flag failures and distant gaps as transparent. Recorded footprint corners supply an approximate projection. Photo-specific water/cloud masks are unavailable and independent pixel registration is not validated. Usable display coverage ranges from 16.5% to 75.7%; the UI shows each layer’s coverage. These are satellite observations, not model-generated spatial predictions. Producing defensible model concentration maps still requires aligned spatial supervision and held-out spatial validation.

Local verification: `runtime/evidence-pilot-verification.json`; full generator log: `runtime/evidence-pilot-build.log`. The frontend validates crop and model identity before displaying a pilot artifact.

Pilot production deployment: `dpl_HtMwDuknzrDWGewSfHEkAAw2ndRY`. Production build passed (553 kB JS size advisory). Local browser checks passed for 15-photo selection, a 340 px image cap, region selection, target switching, reference layer, photo-only mode, full-sample browsing, and the non-pilot fallback.

Production Safari verification passed for both target selection and the approximate satellite overlay. The published model-region click updates the numeric explanation. Screenshot: `runtime/evidence-pilot-live.png`.

## Satellite default and confidence display — initial state

Satellite reference is now the first and default pilot layer on initial load and each photo change. The selected-target Prediction confidence panel consumes the existing API prediction-interval status. At that release, sample outputs were explicitly Not calibrated; their held-out model median error factors (1.25× chlorophyll-a, 1.12× Kd(490), rounded) appear separately as model-wide benchmark context. No percentage is inferred from reference agreement, sensitivity, or benchmark error. If the API supplies an available calibrated interval, the panel displays bounds, units, nominal coverage and calibration evidence.

Production build and local browser checks passed for default layer, photo changes and target-specific confidence context.

Published and browser-verified in deployment `dpl_GSZ4tzfrkUsWfLsH1cK8jbgdfmrT`. Screenshot: `runtime/satellite-confidence-live.png`.


## Calibrated confidence and photos without references

The current confidence work supersedes the initial uncalibrated panel above. Models predict from the photo and metadata without satellite target values. Separate reference-bearing scenes fit and evaluate confidence probabilities, defined as agreement within ±25%. Supported scores are displayed for matched and unmatched photos; unsupported bands remain unavailable.

The explanation pilot now contains 18 photos, including three without satellite references. Those three default to model sensitivity. The 15 with reference layers still default to the satellite view. See [the confidence release report](confidence-release-2026-11-03.md) for target-level results, limitations, independent partitions, and verification.
