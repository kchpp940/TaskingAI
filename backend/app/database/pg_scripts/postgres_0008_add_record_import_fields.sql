-- Add import status fields to record table
ALTER TABLE record ADD COLUMN IF NOT EXISTS processing_stage TEXT;
ALTER TABLE record ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE record ADD COLUMN IF NOT EXISTS import_params JSONB DEFAULT '{}';

CREATE INDEX IF NOT EXISTS record_status_idx ON record (status);
CREATE INDEX IF NOT EXISTS record_processing_stage_idx ON record (processing_stage);
