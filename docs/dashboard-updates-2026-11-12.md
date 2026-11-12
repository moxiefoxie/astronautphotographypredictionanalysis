# Dashboard changes — 12 November 2026

Implemented locally; the existing public frontend and API have not been redeployed.

- Paired satellite matrices and astronaut-photo overlays for all 50 matched photos in the hosted Mediterranean sample and six native-pixel examples. Both panels share scale, target, and selected cell; photo opacity is adjustable. The matrix exports include NASA photo links and source provenance. Other photos with aggregate references explicitly report when a display matrix is unavailable.
- One significant figure for displayed scientific measurements. Coordinates retain four decimal places; counts, timestamps, method definitions and nominal protocol thresholds remain exact. JSON and binary exports preserve original numeric precision. The focal-length tooltip also gives the exact source value.
- Latitude/longitude plus radius (km), and an interactive OpenStreetMap bounding box selected with two clicks. Both support manual numeric entry, apply/clear actions, and date-line-crossing bounds. Filters operate on recorded photo centers. API radius filtering occurs before count and pagination. Native-photo filtering uses the same spherical distance definition.
- Export complete analyses for every page of the current search, save an entire search to the browser collection, and export the collection with IDs and NASA source links. Failed or changing searches do not download misleading partial results. Source values remain unrounded.
- Display-only focal-length enrichment from NASA frame metadata and public photo pages. All 106 hosted photos have verified page values. A cached, bounded API fallback checks NASA for other selected photos. Stored model inputs and frozen predictions are unchanged.
- Left-aligned images with a semantic metadata table beside them on desktop; stacked layout at smaller widths.
- Optional confidence dialog separating whole-crop, regional, and pixel claims, showing available calibration evidence and unavailable-score reasons.

## Pixel evidence

The native model already consumes RGB arrays from a rectified astronaut photograph. It emits chlorophyll-a and Kd(490) predictions at photo-pixel resolution, but training and evaluation references are larger MODIS regions. Fine detail is not independently validated. RGB values are not chemical concentrations.

Satellite display matrices contain real, quality-masked source measurements, projected using the recorded photo corners. Packaging verifies each source aggregate and valid-pixel count against the saved matchup. All 56 passed. Native granules are checked against their recorded SHA-256 hashes; packaged matrices carry content hashes, and the browser verifies compatibility with the crop and granule. The 32 × 32 display grid uses nearest samples with a gap cutoff. It does not add satellite resolution, fill missing cells, or establish independent geographic registration.

## Verification

- Backend: 38 discovered; 37 passed, one unchanged frozen-model replay test skipped in the lightweight API environment.
- Frontend assertions: radius, bounding box, poles, date line, missing coordinates, rounding, 205-result paginated export, source links, retained precision, and failure handling.
- Production build passed; Vite reports a large main bundle warning.
- Browser: native and satellite maps, shared cell selection, confidence dialog, radius filtering, drawn bounding box, saving a search, and a downloaded JSON export verified. The downloaded record preserved 24 mm focal length, the full prediction, NASA link, and filter snapshot.

Reproduce checks:

```sh
PYTHONPATH=backend DATABASE_URL=sqlite:// .venv/bin/python -m unittest discover -s backend/tests -v
node scripts/test-dashboard.mjs
npm run build
```

To regenerate source artifacts locally (requires the saved research inputs and ML environment):

```sh
python3 scripts/package-photo-metadata.py
.venv/bin/python scripts/refresh-nasa-metadata.py
../kd490_proposal/.venv/bin/python scripts/package-satellite-comparisons.py
```

Deploy the API and frontend together so the new radius parameters and NASA metadata endpoint are available. No database migration, cloud import, retraining, or inference rerun is required.

## Comparison layout revision

The full-width target cards now show predicted pixel/regional ranges and satellite footprint means for both chlorophyll-a and Kd(490), including units and unavailable states. Metadata starts below these cards, beside two equally sized images: predicted overlay and satellite overlay on the photograph. The standalone satellite raster has been removed from the view; its source export remains available.

The native and regional views synchronize target selection and logarithmic color limits. The per-comparison scale spans both available layers; the fixed scale retains consistent limits across photos and labels endpoint clipping. Footprint means are explicitly distinguished from map ranges. Desktop browser checks verified equal image sizes and vertical alignment; the layout stacks at narrow widths.
