-- Additive v1 → v2 migration; no existing table changes.
BEGIN;
CREATE SCHEMA IF NOT EXISTS appa;
SET LOCAL search_path TO appa;

CREATE TABLE IF NOT EXISTS annotation_revisions (
	id VARCHAR NOT NULL,
	photo_id VARCHAR NOT NULL,
	revision INTEGER NOT NULL,
	image_sha256 VARCHAR NOT NULL,
	reviewer VARCHAR NOT NULL,
	created_at VARCHAR NOT NULL,
	regions JSON NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (photo_id, revision),
	FOREIGN KEY(photo_id) REFERENCES photos (id)
)

;
CREATE INDEX IF NOT EXISTS ix_annotation_revisions_photo_id ON annotation_revisions (photo_id);

CREATE TABLE IF NOT EXISTS calibrations (
	id VARCHAR NOT NULL,
	model_id VARCHAR NOT NULL,
	created_at VARCHAR NOT NULL,
	coverage FLOAT NOT NULL,
	log_radius FLOAT NOT NULL,
	manifest JSON NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(model_id) REFERENCES model_versions (id)
)

;
CREATE INDEX IF NOT EXISTS ix_calibrations_model_id ON calibrations (model_id);

CREATE TABLE IF NOT EXISTS overlays (
	id VARCHAR NOT NULL,
	photo_id VARCHAR NOT NULL,
	target VARCHAR NOT NULL,
	image_sha256 VARCHAR NOT NULL,
	model_version VARCHAR NOT NULL,
	created_at VARCHAR NOT NULL,
	manifest JSON NOT NULL,
	payload JSON NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(photo_id) REFERENCES photos (id)
)

;
CREATE INDEX IF NOT EXISTS ix_overlays_photo_id ON overlays (photo_id);
COMMIT;
