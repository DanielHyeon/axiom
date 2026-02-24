-- ============================================================================
-- DDD-P1-04: Service-Specific PostgreSQL Schema Separation
-- ============================================================================
-- Purpose: Move tables from shared `public` schema to service-specific schemas
--          to enforce Bounded Context data ownership.
--
-- Execution: psql -U arkos -d insolvency_os -f 001_schema_separation.sql
--
-- Rollback:  Each service table retains a public.* VIEW for backward compat.
--            To fully revert, drop views, rename tables back to public.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. Create service-specific schemas
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS synapse;
CREATE SCHEMA IF NOT EXISTS vision;
CREATE SCHEMA IF NOT EXISTS weaver;
-- oracle schema already exists (query_history)
CREATE SCHEMA IF NOT EXISTS oracle;

-- ============================================================================
-- 2. Create service-specific DB users with minimal privileges
-- ============================================================================
DO $$
BEGIN
    -- Core service user
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'core_svc') THEN
        CREATE USER core_svc WITH PASSWORD 'core_svc_pwd';
    END IF;
    GRANT USAGE ON SCHEMA core TO core_svc;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA core TO core_svc;
    ALTER DEFAULT PRIVILEGES IN SCHEMA core GRANT ALL ON TABLES TO core_svc;
    ALTER DEFAULT PRIVILEGES IN SCHEMA core GRANT ALL ON SEQUENCES TO core_svc;

    -- Synapse service user
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'synapse_svc') THEN
        CREATE USER synapse_svc WITH PASSWORD 'synapse_svc_pwd';
    END IF;
    GRANT USAGE ON SCHEMA synapse TO synapse_svc;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA synapse TO synapse_svc;
    ALTER DEFAULT PRIVILEGES IN SCHEMA synapse GRANT ALL ON TABLES TO synapse_svc;
    ALTER DEFAULT PRIVILEGES IN SCHEMA synapse GRANT ALL ON SEQUENCES TO synapse_svc;

    -- Vision service user
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'vision_svc') THEN
        CREATE USER vision_svc WITH PASSWORD 'vision_svc_pwd';
    END IF;
    GRANT USAGE ON SCHEMA vision TO vision_svc;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA vision TO vision_svc;
    ALTER DEFAULT PRIVILEGES IN SCHEMA vision GRANT ALL ON TABLES TO vision_svc;
    ALTER DEFAULT PRIVILEGES IN SCHEMA vision GRANT ALL ON SEQUENCES TO vision_svc;

    -- Weaver service user
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'weaver_svc') THEN
        CREATE USER weaver_svc WITH PASSWORD 'weaver_svc_pwd';
    END IF;
    GRANT USAGE ON SCHEMA weaver TO weaver_svc;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA weaver TO weaver_svc;
    ALTER DEFAULT PRIVILEGES IN SCHEMA weaver GRANT ALL ON TABLES TO weaver_svc;
    ALTER DEFAULT PRIVILEGES IN SCHEMA weaver GRANT ALL ON SEQUENCES TO weaver_svc;

    -- Oracle service user
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'oracle_svc') THEN
        CREATE USER oracle_svc WITH PASSWORD 'oracle_svc_pwd';
    END IF;
    GRANT USAGE ON SCHEMA oracle TO oracle_svc;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA oracle TO oracle_svc;
    ALTER DEFAULT PRIVILEGES IN SCHEMA oracle GRANT ALL ON TABLES TO oracle_svc;
    ALTER DEFAULT PRIVILEGES IN SCHEMA oracle GRANT ALL ON SEQUENCES TO oracle_svc;
END
$$;

-- ============================================================================
-- 3. Migrate Core tables: public -> core.*
-- ============================================================================

-- 3a. tenants
ALTER TABLE IF EXISTS public.tenants SET SCHEMA core;
CREATE OR REPLACE VIEW public.tenants AS SELECT * FROM core.tenants;

-- 3b. users
ALTER TABLE IF EXISTS public.users SET SCHEMA core;
CREATE OR REPLACE VIEW public.users AS SELECT * FROM core.users;

-- 3c. event_outbox
ALTER TABLE IF EXISTS public.event_outbox SET SCHEMA core;
CREATE OR REPLACE VIEW public.event_outbox AS SELECT * FROM core.event_outbox;

-- 3d. bpm_work_item
ALTER TABLE IF EXISTS public.bpm_work_item SET SCHEMA core;
CREATE OR REPLACE VIEW public.bpm_work_item AS SELECT * FROM core.bpm_work_item;

-- 3e. bpm_process_definition
ALTER TABLE IF EXISTS public.bpm_process_definition SET SCHEMA core;
CREATE OR REPLACE VIEW public.bpm_process_definition AS SELECT * FROM core.bpm_process_definition;

-- 3f. bpm_process_role_binding
ALTER TABLE IF EXISTS public.bpm_process_role_binding SET SCHEMA core;
CREATE OR REPLACE VIEW public.bpm_process_role_binding AS SELECT * FROM core.bpm_process_role_binding;

-- 3g. core_case
ALTER TABLE IF EXISTS public.core_case SET SCHEMA core;
CREATE OR REPLACE VIEW public.core_case AS SELECT * FROM core.core_case;

-- 3h. core_case_activity
ALTER TABLE IF EXISTS public.core_case_activity SET SCHEMA core;
CREATE OR REPLACE VIEW public.core_case_activity AS SELECT * FROM core.core_case_activity;

-- 3i. core_document_review
ALTER TABLE IF EXISTS public.core_document_review SET SCHEMA core;
CREATE OR REPLACE VIEW public.core_document_review AS SELECT * FROM core.core_document_review;

-- 3j. watch_subscriptions
ALTER TABLE IF EXISTS public.watch_subscriptions SET SCHEMA core;
CREATE OR REPLACE VIEW public.watch_subscriptions AS SELECT * FROM core.watch_subscriptions;

-- 3k. watch_rules
ALTER TABLE IF EXISTS public.watch_rules SET SCHEMA core;
CREATE OR REPLACE VIEW public.watch_rules AS SELECT * FROM core.watch_rules;

-- 3l. watch_alerts (depends on watch_subscriptions FK)
ALTER TABLE IF EXISTS public.watch_alerts SET SCHEMA core;
CREATE OR REPLACE VIEW public.watch_alerts AS SELECT * FROM core.watch_alerts;

-- ============================================================================
-- 4. Synapse tables: public -> synapse.*
--    (Synapse uses raw SQL CREATE TABLE IF NOT EXISTS; tables may not yet exist)
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='event_logs') THEN
        ALTER TABLE public.event_logs SET SCHEMA synapse;
        CREATE OR REPLACE VIEW public.event_logs AS SELECT * FROM synapse.event_logs;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='schema_tables') THEN
        ALTER TABLE public.schema_tables SET SCHEMA synapse;
        CREATE OR REPLACE VIEW public.schema_tables AS SELECT * FROM synapse.schema_tables;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='schema_columns') THEN
        ALTER TABLE public.schema_columns SET SCHEMA synapse;
        CREATE OR REPLACE VIEW public.schema_columns AS SELECT * FROM synapse.schema_columns;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='schema_relationships') THEN
        ALTER TABLE public.schema_relationships SET SCHEMA synapse;
        CREATE OR REPLACE VIEW public.schema_relationships AS SELECT * FROM synapse.schema_relationships;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='mining_tasks') THEN
        ALTER TABLE public.mining_tasks SET SCHEMA synapse;
        CREATE OR REPLACE VIEW public.mining_tasks AS SELECT * FROM synapse.mining_tasks;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='mining_results') THEN
        ALTER TABLE public.mining_results SET SCHEMA synapse;
        CREATE OR REPLACE VIEW public.mining_results AS SELECT * FROM synapse.mining_results;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='mining_models') THEN
        ALTER TABLE public.mining_models SET SCHEMA synapse;
        CREATE OR REPLACE VIEW public.mining_models AS SELECT * FROM synapse.mining_models;
    END IF;
END
$$;

-- ============================================================================
-- 5. Vision tables: public -> vision.*
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='what_if_scenarios') THEN
        ALTER TABLE public.what_if_scenarios SET SCHEMA vision;
        CREATE OR REPLACE VIEW public.what_if_scenarios AS SELECT * FROM vision.what_if_scenarios;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='cubes') THEN
        ALTER TABLE public.cubes SET SCHEMA vision;
        CREATE OR REPLACE VIEW public.cubes AS SELECT * FROM vision.cubes;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='etl_jobs') THEN
        ALTER TABLE public.etl_jobs SET SCHEMA vision;
        CREATE OR REPLACE VIEW public.etl_jobs AS SELECT * FROM vision.etl_jobs;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='root_cause_analyses') THEN
        ALTER TABLE public.root_cause_analyses SET SCHEMA vision;
        CREATE OR REPLACE VIEW public.root_cause_analyses AS SELECT * FROM vision.root_cause_analyses;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='vision_analytics_kpi') THEN
        ALTER TABLE public.vision_analytics_kpi SET SCHEMA vision;
        CREATE OR REPLACE VIEW public.vision_analytics_kpi AS SELECT * FROM vision.vision_analytics_kpi;
    END IF;
END
$$;

-- ============================================================================
-- 6. Weaver tables: public -> weaver.*
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='weaver_metadata_datasources') THEN
        ALTER TABLE public.weaver_metadata_datasources SET SCHEMA weaver;
        CREATE OR REPLACE VIEW public.weaver_metadata_datasources AS SELECT * FROM weaver.weaver_metadata_datasources;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='weaver_metadata_snapshots') THEN
        ALTER TABLE public.weaver_metadata_snapshots SET SCHEMA weaver;
        CREATE OR REPLACE VIEW public.weaver_metadata_snapshots AS SELECT * FROM weaver.weaver_metadata_snapshots;
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name='weaver_metadata_glossary_terms') THEN
        ALTER TABLE public.weaver_metadata_glossary_terms SET SCHEMA weaver;
        CREATE OR REPLACE VIEW public.weaver_metadata_glossary_terms AS SELECT * FROM weaver.weaver_metadata_glossary_terms;
    END IF;
END
$$;

-- ============================================================================
-- 7. Oracle — already using oracle.* schema, nothing to migrate
-- ============================================================================

-- ============================================================================
-- 8. Verification query
-- ============================================================================
SELECT
    schemaname AS schema,
    tablename AS table_name,
    'TABLE' AS type
FROM pg_tables
WHERE schemaname IN ('core', 'synapse', 'vision', 'weaver', 'oracle')
ORDER BY schemaname, tablename;

COMMIT;
