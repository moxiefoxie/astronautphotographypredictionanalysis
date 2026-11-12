-- Initial v1 schema. Run once on PostgreSQL, using an owner/migration account.

CREATE SCHEMA IF NOT EXISTS appa;

SET search_path TO appa;

CREATE TABLE photos (
	id VARCHAR NOT NULL,
	captured_at VARCHAR,
	latitude FLOAT,
	longitude FLOAT,
	mission VARCHAR NOT NULL,
	thumbnail_url VARCHAR NOT NULL,
	image_url VARCHAR NOT NULL,
	original_url VARCHAR NOT NULL,
	metadata_json JSON NOT NULL,
	local_image VARCHAR,
	image_sha256 VARCHAR,
	PRIMARY KEY (id)
);

CREATE INDEX ix_photos_mission ON photos (mission);

CREATE INDEX ix_photos_captured_at ON photos (captured_at);

CREATE INDEX ix_photos_latitude ON photos (latitude);

CREATE TABLE model_versions (
	id VARCHAR NOT NULL,
	target VARCHAR NOT NULL,
	name VARCHAR NOT NULL,
	units VARCHAR NOT NULL,
	manifest JSON NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE prediction_runs (
	id VARCHAR NOT NULL,
	kind VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	created_at VARCHAR NOT NULL,
	completed_at VARCHAR,
	provenance JSON NOT NULL,
	PRIMARY KEY (id)
);

CREATE INDEX ix_prediction_runs_status ON prediction_runs (status);

CREATE TABLE satellite_matchups (
	id VARCHAR NOT NULL,
	photo_id VARCHAR NOT NULL,
	dataset_sha256 VARCHAR NOT NULL,
	data JSON NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(photo_id) REFERENCES photos (id)
);

CREATE INDEX ix_satellite_matchups_photo_id ON satellite_matchups (photo_id);

CREATE TABLE jobs (
	id VARCHAR NOT NULL,
	idempotency_key VARCHAR NOT NULL,
	photo_id VARCHAR NOT NULL,
	run_id VARCHAR NOT NULL,
	model_ids JSON NOT NULL,
	status VARCHAR NOT NULL,
	attempts INTEGER NOT NULL,
	created_at VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	lease_until FLOAT,
	lease_token VARCHAR,
	error VARCHAR,
	PRIMARY KEY (id),
	UNIQUE (idempotency_key),
	FOREIGN KEY(photo_id) REFERENCES photos (id),
	FOREIGN KEY(run_id) REFERENCES prediction_runs (id)
);

CREATE INDEX ix_jobs_status ON jobs (status);

CREATE TABLE estimates (
	id VARCHAR NOT NULL,
	photo_id VARCHAR NOT NULL,
	run_id VARCHAR NOT NULL,
	model_id VARCHAR NOT NULL,
	matchup_id VARCHAR,
	target VARCHAR NOT NULL,
	value FLOAT NOT NULL,
	role VARCHAR NOT NULL,
	split VARCHAR,
	scene_group VARCHAR,
	created_at VARCHAR NOT NULL,
	evidence JSON NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (run_id, photo_id, model_id),
	CONSTRAINT positive_estimate CHECK (value > 0),
	FOREIGN KEY(photo_id) REFERENCES photos (id),
	FOREIGN KEY(run_id) REFERENCES prediction_runs (id),
	FOREIGN KEY(model_id) REFERENCES model_versions (id),
	FOREIGN KEY(matchup_id) REFERENCES satellite_matchups (id)
);

CREATE INDEX ix_estimates_run_id ON estimates (run_id);

CREATE INDEX ix_estimates_split ON estimates (split);

CREATE INDEX ix_estimates_photo_id ON estimates (photo_id);

CREATE INDEX ix_estimates_role ON estimates (role);
