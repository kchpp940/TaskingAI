-- Add independent import status fields to record table (separate from lifecycle status)
ALTER TABLE record ADD COLUMN IF NOT EXISTS import_status TEXT;
ALTER TABLE record ADD COLUMN IF NOT EXISTS processing_stage TEXT;
ALTER TABLE record ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE record ADD COLUMN IF NOT EXISTS import_params JSONB DEFAULT '{}';
ALTER TABLE record ADD COLUMN IF NOT EXISTS import_attempt_id TEXT;

-- Backfill import_status for existing records: if lifecycle status is ready, mark as succeeded
UPDATE record SET import_status = 'succeeded' WHERE import_status IS NULL AND status = 'ready';

CREATE INDEX IF NOT EXISTS record_import_status_idx ON record (import_status);
CREATE INDEX IF NOT EXISTS record_processing_stage_idx ON record (processing_stage);
CREATE INDEX IF NOT EXISTS record_import_attempt_id_idx ON record (import_attempt_id);
