# APPA feature decisions — updated 3 November 2026

Cloud destination: **APPA Sample**, `qcjkgrelvnivgpfwrfan`, in moxiefoxie's Org on the Free plan. The old review project is preserved. Johann's Geolocation project `zwdkkwbxlsrlqsqjfdht` is a read-only source. It is not the APPA application database.

The first release uses real, versioned source exports and verified model outputs. A snapshot is not a live catalog feed. Johann's currently available publishable key returned no photo rows under its existing access policy. Authenticated dashboard queries work; an automated feed needs an authorized read-only API policy/credential or a scheduled export. No database-owner password is needed for a properly authorized Data API feed.

The cloud release is limited to 100 Mediterranean photos and 50 satellite matchups. New model runs append compact estimates while preserving the original 200 outputs. The larger counts below describe the verified local archive, not the cloud sample. No image bytes or experimental overlays are imported.

## Keep and connect now

| Feature | Decision and evidence |
| --- | --- |
| Search, pagination, mission/date/split filters | Real database queries. A cohort filter separates the Mediterranean test set from the original benchmark. |
| Photo and location | NASA identities and images, source timestamps/coordinates, named waters and water/cloud fractions. EarthMatch-verified and orbital-estimate locations remain distinct. |
| Chlorophyll-a and Kd(490) | Import 15,342 saved selected-model outputs for 7,671 Mediterranean test photos. Preserve units, checkpoint hashes, validation selection, input crops and source hashes. |
| Satellite comparisons | Exactly 2,624 Mediterranean photos have suitable references. Preserve flag mask, pixel counts/fractions, overlap, time gap, granule/hash and aggregation. The other 5,047 are inference-only; rejected values are not presented as references. |
| Original benchmark | Retain 2,130 photos, 4,260 frozen estimates and 2,130 references. Existing worker runs are retained separately. Training photos remain labeled in-sample. |
| Model explanation pilot | Eighteen selected photos, including three without satellite references, have 16 region-occlusion experiments per target, reproduced from the exact saved checkpoint and crop. Click a tile to see the measured change; metadata is held fixed. Sensitivity is not concentration or causal attribution. |
| Regional RGB prediction maps | A new model trained on 20,594 regional labels now supplies 289 offshore regional predictions across 11 supported sample photos, including two without satellite references. Mean within-photo pattern error improves versus a flat control, but scene-bootstrap intervals include zero improvement; maps remain experimental. Regional confidence is separately calibrated and only supported Kd bands display percentages. See `spatial-and-uncertainty.md`. |
| Prediction confidence percentages | Supported Kd(490) outputs estimate the probability of ±25% agreement with the satellite-reference definition, using separate calibration/evaluation scenes and fixed reliability checks. A satellite measurement for the current photo is not required. The chlorophyll confidence candidate failed the fixed reliability gates and was not published. See [calibration method and release evidence](confidence-release-2026-11-03.md). |
| Comparison, export, collection | Real values and JSON export. Collections remain browser-local; they are not team-synchronized. |
| Run/model provenance | Persistent records. Versioned source snapshots and input assets avoid overwriting an older prediction's crop evidence. |

## Realistic, but require additional work

| Feature | What is needed |
| --- | --- |
| Interactive new-photo inference | Bounded batch inference works for the sample, including 50 photos without references. Arbitrary uploads and the public queue still need compatible metadata/input adapters and worker integration. Calibration does not require a satellite label for each new photo. |
| Continuous source refresh | A read-only source credential/policy or export schedule. `app.sync_catalog` performs bounded read-only source queries and appends snapshots; it does not rewrite historical metadata or queue the archive. |
| Registered crop previews beyond the sample | The 100-photo sample now has verified compressed crop previews hosted with the frontend. Other cohorts still require artifact hosting. Do not overlay crop-space pixels onto a full original. |
| Confidence intervals | Independent scene-group calibration and coverage evaluation for each exact model version/domain. Geolocation status and test error are not per-photo uncertainty. |
| Water/cloud/hardware segmentation | Some source fractions and mask provenance exist, but the exported mask paths point to another machine. Acquire and verify actual masks and coordinate transforms before displaying them. |
| Pixel-level ocean-color maps | The explanation pilot offers approximate satellite-reference overlays where available, and saved-model occlusion sensitivity even without references. Neither is a validated model concentration map. Acquire photo masks, independently validate registration, and train/evaluate against aligned spatial labels before claiming local retrieval accuracy. |
| Uploads | Trusted ingestion, image storage, per-user authorization, quotas and compatible model workers. Existing operator-only catalog ingestion is not a public upload service. |
| New satellite matchups | Versioned catalog discovery, downloads, registered footprint extraction and quality screening; this is independent of model inference. |
| Shared collections and review teams | Accounts, membership policies and a persistent collection schema. Browser storage is not a substitute. |

## Remove from the current product

| Mock feature | Reason |
| --- | --- |
| Unvalidated confidence percentages | Show only scores supported by the frozen calibration/reliability protocol. Never convert aggregate error factors, EarthMatch inliers, or the current photo’s reference agreement directly into confidence. |
| Usefulness score | No defined, validated reviewer rubric exists. Show concrete availability and quality fields instead. |
| Bloom identification and severity | Chlorophyll estimates and visible color do not establish a confirmed bloom, species, toxicity or severity. Human annotations may be explicitly tentative. |
| Water clarity/condition classes | No validated class thresholds or physical retrieval contract. Show the actual Kd units instead. |
| Fake trend lines, camera/orbit/place values | No matching source series or validated metadata join. Missing values stay missing. |

These decisions remove unsupported claims, not the possibility of implementing a future scientifically justified feature.

The earlier viewer correction defaulted to the photograph, displayed both targets'
confidence together, and separated satellite percentage differences from confidence.
A bounded 18-photo regional inference diagnostic used the scalar checkpoints
without satellite inputs. Ten matched photos had sufficient coverage for scoring:
within-photo contrast skill versus a flat map was 0.68% for chlorophyll and −3.07%
for Kd(490). This exploratory result does not justify publishing tiled scalar
outputs as local retrievals. The subsequent regional RGB model was trained on
regional labels specifically for the dashboard; its experimental maps now form
the default view. Validated dense retrieval remains further work. Both experiments
and their limitations are documented in `spatial-and-uncertainty.md`.
