-- Index added in mod-source-record-manager v4.0.x for get_job_log_entries; built CONCURRENTLY so journal inserts are not blocked.
-- Cannot run inside a transaction block.
\set ON_ERROR_STOP on
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_journal_records_job_entity_source
  ON sul_mod_source_record_manager.journal_records (job_execution_id, entity_type, source_id) INCLUDE (source_record_order, action_type);

-- Should return true; if false, DROP INDEX CONCURRENTLY sul_mod_source_record_manager.idx_journal_records_job_entity_source; and retry.
SELECT indisvalid FROM pg_index
WHERE indexrelid = 'sul_mod_source_record_manager.idx_journal_records_job_entity_source'::regclass;
