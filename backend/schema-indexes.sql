CREATE INDEX IF NOT EXISTS ix_estimates_model_id ON appa.estimates(model_id);
CREATE INDEX IF NOT EXISTS ix_estimates_matchup_id ON appa.estimates(matchup_id);
CREATE INDEX IF NOT EXISTS ix_jobs_photo_id ON appa.jobs(photo_id);
CREATE INDEX IF NOT EXISTS ix_jobs_run_id ON appa.jobs(run_id);
