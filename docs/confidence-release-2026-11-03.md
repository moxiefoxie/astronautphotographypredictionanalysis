# APPA confidence probabilities — 3 November 2026

The model estimates chlorophyll-a and Kd(490) from the recorded photograph crop and its metadata. Satellite target values are **not** inference inputs. They are labels for model training and independent confidence calibration/evaluation. Missing satellite references do not block predictions or confidence.

## Meaning of the percentage

An 80% confidence display means an estimated 80% chance that the numeric estimate is within ±25% of the quality-masked satellite reference definition. It does not mean exact correctness, pixel-level water properties, or agreement with a field measurement. The ±25% tolerance is a product definition, not a claimed scientific standard. Scores are rounded to the nearest five percentage points.

For photos without satellite measurements, accuracy cannot be checked directly. Applying the learned confidence relationship assumes comparable photo quality and input domain. This release is a retrospective Mediterranean study; it does not validate transfer to arbitrary new regions or all reasons for missing references.

## Independent partitions

Fresh ConvNeXt Tiny models start from ImageNet initialization. No older supervised checkpoint is reused. The 20 original training groups with the smallest deterministic SHA-256 rank (`appa-calibration-v1:` plus group ID) are reserved before fitting. Metadata imputation and scaling use only the reduced training partition.

| Partition | Photos | Scene groups | Use |
| --- | ---: | ---: | --- |
| Training | 3,553 | 32 | Fit base model weights |
| Validation | 791 | 12 | Select checkpoint epoch and fit accuracy score |
| Calibration | 2,438 | 20 | Calibrate accuracy probabilities |
| Test | 2,624 | 21 | Retrospective reliability evaluation |

Connected scenes, timelapses, satellite granules, and decoded duplicate pixels cannot cross partitions. Each scene has equal total weight, preventing a long sequence of similar frames from dominating the confidence fit or reliability report. The original test cohort was previously reported for earlier models; it is not a newly collected prospective dataset. Accuracy-score fitting uses base-model validation scenes, so its first stage may reflect checkpoint selection; calibration and evaluation remain separate.

The accuracy score uses log prediction, cloud fraction, water fraction, sun elevation, geolocation source, and footprint area. Its independently fitted sigmoid calibrator uses no current-photo reference values. Portable coefficients reproduce the saved score without a scientific Python runtime in the public API.

The frozen protocol fixes a ±25% event, five probability bins, and release checks before inspecting test results. Overall ECE must be ≤0.12, absolute mean bias ≤0.10, and Brier score no worse than the constant calibration prior plus 0.02. Each displayed band needs at least five test scenes and an absolute confidence/observed-accuracy gap ≤0.15. These are prototype release gates, not statistical guarantees. Scene bootstrap uncertainty is saved in the report.

## Initial Kd(490) release

- Test mean confidence: 69.16%; observed accuracy within ±25%: 74.50%, weighted equally per scene.
- ECE: 0.0793; Brier score: 0.1916 versus constant-prior baseline 0.1976.
- Supported bands: 60–80% and 80–100%. Lower bands failed their predeclared reliability checks and are not displayed.
- Fresh inference ran on all 100 sample photos without satellite values: 50 matched and 50 without usable references.
- Confidence available: 89/100 (41 matched, **48 without references**). Unsupported scores stay unavailable; numeric predictions remain visible.
- Live example: `ISS042-E-104322`, no reference, Kd(490) about 0.0386 m⁻¹, displayed confidence 80%.

## Chlorophyll candidate — rejected, not published

The fresh full ConvNeXt model completed all 12 training epochs, selecting epoch 9 using validation scenes only. Its confidence calibration failed the frozen test gates:

- ECE 0.1397 exceeded the 0.12 limit.
- Brier score 0.2716 exceeded the constant-prior baseline 0.2418 plus the allowed 0.02.
- The 60–80% band averaged 65.04% predicted confidence but only 11.12% observed agreement within ±25%, across eight evaluation scene groups.
- Overall scene-weighted ±25% accuracy was 40.94%, versus 44.82% predicted confidence. Aggregate mean agreement alone did not reveal the poor ranking/reliability of particular bands.

The protocol and gates were not changed after seeing these results. The release builder refused to publish the target. The existing chlorophyll model and estimates remain live, with an explicit notice that the new confidence candidate did not pass. These failed-candidate statistics must not be represented as performance of the older model currently shown in the dashboard.

Inference with the new candidate nevertheless succeeded on all 100 sample photos, including 50 without references, with a maximum benchmark replay difference of 2.98e-7 log10 units. Missing satellite labels are not the blocker. A future confidence method needs better ability to predict model errors and a new independent evaluation cohort; retuning against this now-inspected test set would not provide independent validation. More varied calibration scenes and photo-derived uncertainty signals are possible next investigations, not claimed fixes. The rejected checkpoint, coefficients, reports and sample outputs remain local for audit.

## Serving and storage

Each saved confidence proof binds the exact model, numeric prediction, input crop hash, scene, feature vector, calibration version, and approved reliability band. Training/calibration images, changed crops or predictions, malformed features, and unsupported bands cannot claim a score. References are optional in this verification. The current public release serves audited saved inference; arbitrary upload/worker inference remains disabled pending its metadata/input adapter.

The APPA Sample project (`qcjkgrelvnivgpfwrfan`) receives only one new model, one run, and 100 compact estimates per released target. Each bundle is capped at 512 KiB. Append-only staging preserves existing estimates and crops. Activation occurs after matching frontend evidence and API code are deployed. No schema change, bulk catalogue copy, image upload to Supabase, paid plan, or writes to Johann's source database are required.

The explanation pilot includes 15 photos with reference layers and three without references (`ISS042-E-104322`, `ISS051-E-22628`, `ISS051-E-33543`). Missing-reference photos default to model sensitivity; reference-enabled photos default to the satellite layer.

Model sensitivity layers are replayed against the new checkpoint before activation. The frontend selects evidence matching both target model IDs and the input crop, with previous versions retained during deployment. Satellite layers remain independent, approximately aligned references; neither these layers nor occlusion sensitivity is a predicted concentration map.

## Reproduction

Training and calibration artifacts: `../../appa_calibration_20261103/` (local, excluded from deployment). Scripts: `train-calibration-models.py`, `calibrate-confidence.py`, `infer-calibrated-sample.py`, `build-confidence-release.py`, `build-evidence-pilot.py` in `../scripts/`.

Release commands use `PYTHONPATH=backend .venv/bin/python -m app.confidence_release runtime/confidence-release-<target>.json`; default is offline preflight. `--apply` stages; `--apply --activate` verifies exact round trips and activates. The tool refuses any destination except the user's APPA Sample project, conflicting historical records, a changed sample, missing dependencies, or excessive database size.

Backend regression tests include absent satellite references, immutable input/model verification, scene weighting, tolerance boundaries, corrupted confidence features, and unsupported reliability bins. Public browser verification confirms confidence and “Satellite reference: Unavailable” together on the same photo.


## Final verification

The public release contains 300 stored estimates: the original 200 plus 100 new Kd(490) outputs. No rejected chlorophyll candidate records were inserted. Backend suite: 35 tests run, one optional original-checkpoint ML test skipped; all remaining tests passed. All 18 pilot artifacts replay the selected current models within 4.18e-7 log10 units. Public API checks cover the three inference-only explanation photos, a referenced photo, and an unsupported Kd confidence band.

Final production deployment: frontend `dpl_CrV4DPMxcrsWUpup4HTtAk9NHQqZ`; API `dpl_GccV7dyfb9Y8DDGjZFPjxdvQCEKT`. Both reported READY. Database verification: 100 photos, 300 estimates, 50 matchups, two completed runs, zero pending runs; 13,326,003 bytes. Supabase security advisor returned no lints.

Public browser verification confirmed the rejected-candidate explanation for chlorophyll and, on `ISS042-E-104322`, Kd(490) confidence of 80% with satellite reference unavailable, a disabled satellite-layer control, and 16 interactive sensitivity regions. Screenshot: `../runtime/confidence-without-reference-final.png`. Full public parity report: `../runtime/confidence-release-verification.json`.
