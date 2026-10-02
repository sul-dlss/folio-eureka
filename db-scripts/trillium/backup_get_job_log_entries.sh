#!/bin/sh
# Save the current get_job_log_entries and get_entity_status definitions before applying the v4.0.5 backport.
# Rollback: psql -h $DB_HOST -p $DB_PORT -U $DB_USERNAME -d $DB_DATABASE -v ON_ERROR_STOP=1 -1 -f get_job_log_entries_3.10.12_backup.sql
set -e
psql -h $DB_HOST -p $DB_PORT -U $DB_USERNAME -d $DB_DATABASE -Atc "SELECT pg_get_functiondef('sul_mod_source_record_manager.get_job_log_entries(uuid,text,text,bigint,bigint,boolean,text)'::regprocedure) || ';'" > get_job_log_entries_3.10.12_backup.sql
psql -h $DB_HOST -p $DB_PORT -U $DB_USERNAME -d $DB_DATABASE -Atc "SELECT pg_get_functiondef('sul_mod_source_record_manager.get_entity_status(text[],bigint)'::regprocedure) || ';'" >> get_job_log_entries_3.10.12_backup.sql
wc -l get_job_log_entries_3.10.12_backup.sql
