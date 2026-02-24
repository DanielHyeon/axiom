-- ============================================================================
-- ROLLBACK: DDD-P1-04 Schema Separation
-- ============================================================================
-- Reverts all tables from service-specific schemas back to public.
-- Run: psql -U arkos -d insolvency_os -f 001_schema_separation_rollback.sql
-- ============================================================================

BEGIN;

-- Drop compatibility views first (they reference the schema tables)
DO $$
DECLARE
    v RECORD;
BEGIN
    FOR v IN
        SELECT table_schema, table_name
        FROM information_schema.views
        WHERE table_schema = 'public'
          AND table_name IN (
            'tenants', 'users', 'event_outbox',
            'bpm_work_item', 'bpm_process_definition', 'bpm_process_role_binding',
            'core_case', 'core_case_activity', 'core_document_review',
            'watch_subscriptions', 'watch_rules', 'watch_alerts',
            'event_logs', 'schema_tables', 'schema_columns', 'schema_relationships',
            'mining_tasks', 'mining_results', 'mining_models',
            'what_if_scenarios', 'cubes', 'etl_jobs', 'root_cause_analyses', 'vision_analytics_kpi',
            'weaver_metadata_datasources', 'weaver_metadata_snapshots', 'weaver_metadata_glossary_terms'
          )
    LOOP
        EXECUTE format('DROP VIEW IF EXISTS public.%I CASCADE', v.table_name);
    END LOOP;
END
$$;

-- Move Core tables back
DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'tenants', 'users', 'event_outbox',
        'bpm_work_item', 'bpm_process_definition', 'bpm_process_role_binding',
        'core_case', 'core_case_activity', 'core_document_review',
        'watch_subscriptions', 'watch_rules', 'watch_alerts'
    ] LOOP
        IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='core' AND table_name=t) THEN
            EXECUTE format('ALTER TABLE core.%I SET SCHEMA public', t);
        END IF;
    END LOOP;
END
$$;

-- Move Synapse tables back
DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'event_logs', 'schema_tables', 'schema_columns', 'schema_relationships',
        'mining_tasks', 'mining_results', 'mining_models'
    ] LOOP
        IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='synapse' AND table_name=t) THEN
            EXECUTE format('ALTER TABLE synapse.%I SET SCHEMA public', t);
        END IF;
    END LOOP;
END
$$;

-- Move Vision tables back
DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'what_if_scenarios', 'cubes', 'etl_jobs', 'root_cause_analyses', 'vision_analytics_kpi'
    ] LOOP
        IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='vision' AND table_name=t) THEN
            EXECUTE format('ALTER TABLE vision.%I SET SCHEMA public', t);
        END IF;
    END LOOP;
END
$$;

-- Move Weaver tables back
DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'weaver_metadata_datasources', 'weaver_metadata_snapshots', 'weaver_metadata_glossary_terms'
    ] LOOP
        IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='weaver' AND table_name=t) THEN
            EXECUTE format('ALTER TABLE weaver.%I SET SCHEMA public', t);
        END IF;
    END LOOP;
END
$$;

COMMIT;
