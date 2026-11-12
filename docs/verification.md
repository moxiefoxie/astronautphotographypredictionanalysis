# Verification — 2026-10-09

- Frontend production build: passed (`npm run build`).
- API/queue/catalog suite: 13 tests passed in the API environment. Includes authentication, date/availability filters, pagination, idempotency, concurrent claims, crash recovery, stale-worker fencing, retry exhaustion, atomic rollback, finite output validation, duplicate-image exposure, and new-catalog input gates.
- Real-checkpoint regression test: passed in the existing NASA ML environment. Nine photos spanning all three splits; 18 target values compared at relative tolerance 1e-5. Observed maximum relative error on the sampled replay: 2.7449e-7.
- API → database job → independent worker → persisted result: passed for ISS005-E-11615. Both estimates committed; history grew from two to four outputs; training exposure retained. Repeated request key returned the same job.
- Frozen import retry: skipped cleanly without duplicating any benchmark rows.
- Browser checks: real photo/satellite values loaded, exact-ID search, no-results state, 350-photo held-out filter, browser collection, comparison dialog, JSON export action, and responsive/desktop rendering.
- Initial benchmark: 2,130 photos, 2,130 matchups, 4,260 estimates. The verification inference adds two outputs and one run to the local database.
- Current local preview: http://127.0.0.1:5173; screenshot saved in ignored runtime/dashboard-preview.jpg.

Not verified: a live PostgreSQL migration, Supabase connectivity, Vercel build/runtime deployment, or sustained production load. The configured legacy Supabase hostname failed DNS resolution from this environment and dashboard access requires sign-in. The cloud deployment must remain separate from the verified local implementation.

## Spatial and uncertainty verification — 2026-10-09

- Backfilled both experimental target layers for all 2,130 photos (4,260 distinct photo/target pairs), zero generation failures. Earlier encoding-version artifacts remain retained (5,204 versioned layer rows total).
- 23 API/catalog/spatial tests passed; the optional existing ML replay test was skipped in the API environment. New tests cover PNG/grid serving, source-hash filtering, authenticated annotation writes, revision/idempotency conflicts, history retention, invalid polygons, exact finite-sample quantile, duplicate-image/benchmark leakage, shared-granule grouping, domain eligibility, and spatial-failure isolation from scalar completion.
- Both `ISS074-E-584783` experimental maps match the frozen NPZ exports with identical valid-pixel masks and maximum log10 errors below 5.01e-6 (the documented five-decimal JSON rounding).
- Local HTTP smoke checks passed for health, spatial metadata, both PNG assets, decompressed grid values and calibration inventory.
- Browser verified layer switching, pixel readout, keyboard opacity change, three-point polygon completion, draft recovery after photo switching, and discard. Mobile viewport 390 px had no horizontal overflow; desktop layout also inspected. Test polygon was discarded; no test annotations or synthetic calibrations were saved in the live database.
- Production frontend build passed. Vite reports its usual approximately 501 kB single-chunk size advisory; this is not a build failure.
- No independent scientific calibration cohort was supplied or generated. Numerical interval coverage is not yet evaluated and no intervals were assigned to benchmark photos. Vercel/Supabase deployment was not performed.
