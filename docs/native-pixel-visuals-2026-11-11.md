# Native-pixel visual update — 11 November 2026

## Dashboard integration corrected

The separate native-map gallery and default tab were removed after the user clarified that only overlay generation should change. APPA retains its original Explore imagery, Prediction runs, and Collection views. The six native maps are available through the existing Cohort selector as “High-density subset” and render inside the original photo analysis panel, with its metadata, readiness, whole-crop benchmark/satellite comparisons, actions, and provenance intact. The database-backed cohorts still use the existing API.

The six local photo detail records are generated from the frozen selected-photo catalog, verified scalar predictions, and satellite matchups; missing fields remain unavailable. Scalar model outputs are explicitly separate from pixel overlay estimates. No database writes or Supabase uploads were performed. The local API serializer now tolerates models whose confidence calibration is null, preserving the private-field exclusion for populated calibration records.

## Current version: full-photo inference

The user correctly identified the large boxes remaining in the first preview. Two causes were present: independently normalized 128-pixel inference cores, and a coarse 8×8 support mask. `high_density_pixel_20261109/export_fullframe.py` now produces `maps_fullframe_v2` without changing model weights, training contracts, cohort membership, or original exports. Each image receives one full-resolution forward pass with a 16-pixel outer halo and trailing alignment padding. There are no internal inference tiles, blended tiles, replicated regional values, or post-prediction blur.

Support is now computed at each native pixel: a 2 km shoreline exclusion plus a conservative pixel-radius bound, original brightness/saturation thresholds applied over a moving 5×5 all-pass neighborhood, and a local p95-minus-median brightness check. This is a new inference mask heuristic, not a validated replacement for cloud/hardware detection or a claim that all newly displayed pixels match the old training domain. Original coarse training/reference quality checks are unchanged.

The same fixed 25 held-out photos (100 regional references, 20 groups) were reevaluated using full-photo outputs pooled over original reference bounds. Group-balanced log10 MAE changes from 0.341 to 0.379 for chlorophyll-a and 0.211 to 0.228 for Kd(490), versus constant-baseline errors of 0.414 and 0.250. Neither finer physical accuracy nor improved regional accuracy is claimed. These new scores are shown in the viewer; the original results remain intact.

All six maps passed full-frame replay, native dimensions, NPZ round trips and alpha/support equality. The new frontend package is 16,219,115 bytes including browser arrays and NPZ downloads. Build and visual inspection confirm that the coarse squares and patch seams are absent. Repackage with `scripts/package-native-maps.py --fullframe`. Source provenance and checks are in `maps_fullframe_v2/contract.json` and `verification.json`. Still local only, pending the existing hardware review before publication.

## Initial preview (superseded)

The default APPA view now displays the six verified held-out maps from `high_density_pixel_20261109`. The earlier Mediterranean regional maps and database-backed imagery remain in their own tab. Native maps do not depend on API availability and do not add Supabase rows or storage objects.

Each view provides chlorophyll-a/Kd(490) switching, photo/overlay/prediction modes, opacity, fit/native/2×/4× zoom, fixed logarithmic colour scales, original float32 pixel inspection, masked-area explanations, and NPZ/PNG/provenance downloads. A scene change resets the viewer and cancels outstanding pixel-data requests. Pixel values are checked against their SHA-256 before display.

`scripts/package-native-maps.py` checks the source completion audits and asset hashes, copies the exact verified rasters, and emits little-endian float32 browser arrays without changing scientific values. The six packages total 13,824,154 bytes, including download arrays. Their PNG dimensions and alpha masks match the original exports. The frontend bundle is built with these assets.

Verification: production build passed; all six binary arrays exactly match source NPZ values, including missing-value masks; all raster dimensions and alpha masks match; all assets exist in the build. Browser checks covered target switching, scene switching, photo-only mode, zoom, a valid pixel reading, and an excluded-area reading. The new default view works without the API.

Release status: local preview only, not deployed. The frozen run protocol requires manual hardware-obstruction review before publication. Finer output spacing does not validate finer physical accuracy. Offshore support boundaries remain block-shaped, and some predictions exhibit tile seams; those seams must not be represented as confirmed water structure. No smoothing was applied to hide either limitation.
