-- Additive v2 → v3: source snapshots and versioned model inputs.

BEGIN;

SET LOCAL search_path TO appa;


CREATE TABLE IF NOT EXISTS catalog_snapshots (
	id VARCHAR NOT NULL,
	photo_id VARCHAR NOT NULL,
	source VARCHAR NOT NULL,
	imported_at VARCHAR NOT NULL,
	data JSON NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(photo_id) REFERENCES photos (id)
)

;

CREATE INDEX IF NOT EXISTS ix_catalog_snapshots_photo_id ON catalog_snapshots (photo_id);


CREATE TABLE IF NOT EXISTS input_assets (
	id VARCHAR NOT NULL,
	photo_id VARCHAR NOT NULL,
	image_sha256 VARCHAR NOT NULL,
	local_path VARCHAR,
	kind VARCHAR NOT NULL,
	provenance JSON NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(photo_id) REFERENCES photos (id)
)

;

CREATE INDEX IF NOT EXISTS ix_input_assets_image_sha256 ON input_assets (image_sha256);

CREATE INDEX IF NOT EXISTS ix_input_assets_photo_id ON input_assets (photo_id);

ALTER TABLE appa.model_versions ENABLE ROW LEVEL SECURITY;

ALTER TABLE appa.photos ENABLE ROW LEVEL SECURITY;

ALTER TABLE appa.prediction_runs ENABLE ROW LEVEL SECURITY;

ALTER TABLE appa.annotation_revisions ENABLE ROW LEVEL SECURITY;

ALTER TABLE appa.calibrations ENABLE ROW LEVEL SECURITY;

ALTER TABLE appa.catalog_snapshots ENABLE ROW LEVEL SECURITY;

ALTER TABLE appa.input_assets ENABLE ROW LEVEL SECURITY;

ALTER TABLE appa.jobs ENABLE ROW LEVEL SECURITY;

ALTER TABLE appa.overlays ENABLE ROW LEVEL SECURITY;

ALTER TABLE appa.satellite_matchups ENABLE ROW LEVEL SECURITY;

ALTER TABLE appa.estimates ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON SCHEMA appa FROM PUBLIC, anon, authenticated;

REVOKE ALL ON ALL TABLES IN SCHEMA appa FROM PUBLIC, anon, authenticated;

COMMIT;
