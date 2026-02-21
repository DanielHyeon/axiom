import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://arkos:arkos@localhost:5432/insolvency_os")


SQL_STATEMENTS = [
    # Process constraints
    """
    DO $$
    BEGIN
      IF to_regclass('public.bpm_process_definition') IS NOT NULL
         AND NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_bpm_process_definition_tenant_name_version'
      ) THEN
        ALTER TABLE bpm_process_definition
        ADD CONSTRAINT uq_bpm_process_definition_tenant_name_version
        UNIQUE (tenant_id, name, version);
      END IF;
    END$$;
    """,
    """
    DO $$
    BEGIN
      IF to_regclass('public.bpm_process_role_binding') IS NOT NULL
         AND NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_bpm_process_role_binding_proc_role_tenant'
      ) THEN
        ALTER TABLE bpm_process_role_binding
        ADD CONSTRAINT uq_bpm_process_role_binding_proc_role_tenant
        UNIQUE (proc_inst_id, role_name, tenant_id);
      END IF;
    END$$;
    """,
    # Watch constraints
    """
    DO $$
    BEGIN
      IF to_regclass('public.watch_subscriptions') IS NOT NULL
         AND NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_watch_subscriptions_user_evt_case_tenant_active'
      ) THEN
        ALTER TABLE watch_subscriptions
        ADD CONSTRAINT uq_watch_subscriptions_user_evt_case_tenant_active
        UNIQUE (user_id, event_type, case_id, tenant_id, active);
      END IF;
    END$$;
    """,
    """
    DO $$
    BEGIN
      IF to_regclass('public.watch_rules') IS NOT NULL
         AND NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_watch_rules_tenant_name_event'
      ) THEN
        ALTER TABLE watch_rules
        ADD CONSTRAINT uq_watch_rules_tenant_name_event
        UNIQUE (tenant_id, name, event_type);
      END IF;
    END$$;
    """,
    """
    DO $$
    BEGIN
      IF to_regclass('public.watch_alerts') IS NOT NULL
         AND NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_watch_alerts_subscription_id'
      ) THEN
        ALTER TABLE watch_alerts
        ADD CONSTRAINT fk_watch_alerts_subscription_id
        FOREIGN KEY (subscription_id) REFERENCES watch_subscriptions(id)
        ON DELETE SET NULL;
      END IF;
    END$$;
    """,
    # Indexes
    """
    DO $$ BEGIN
      IF to_regclass('public.bpm_work_item') IS NOT NULL THEN
        CREATE INDEX IF NOT EXISTS idx_bpm_work_item_tenant_proc_status ON bpm_work_item (tenant_id, proc_inst_id, status);
        CREATE INDEX IF NOT EXISTS idx_bpm_work_item_tenant_assignee_status ON bpm_work_item (tenant_id, assignee_id, status);
      END IF;
    END $$;
    """,
    """
    DO $$ BEGIN
      IF to_regclass('public.bpm_process_definition') IS NOT NULL THEN
        CREATE INDEX IF NOT EXISTS idx_bpm_process_definition_tenant_created ON bpm_process_definition (tenant_id, created_at);
      END IF;
    END $$;
    """,
    """
    DO $$ BEGIN
      IF to_regclass('public.watch_subscriptions') IS NOT NULL THEN
        CREATE INDEX IF NOT EXISTS idx_watch_subscriptions_tenant_user_active ON watch_subscriptions (tenant_id, user_id, active);
      END IF;
    END $$;
    """,
    """
    DO $$ BEGIN
      IF to_regclass('public.watch_rules') IS NOT NULL THEN
        CREATE INDEX IF NOT EXISTS idx_watch_rules_tenant_event_active ON watch_rules (tenant_id, event_type, active);
      END IF;
    END $$;
    """,
    """
    DO $$ BEGIN
      IF to_regclass('public.watch_alerts') IS NOT NULL THEN
        CREATE INDEX IF NOT EXISTS idx_watch_alerts_tenant_status_triggered ON watch_alerts (tenant_id, status, triggered_at);
        CREATE INDEX IF NOT EXISTS idx_watch_alerts_tenant_unread_triggered ON watch_alerts (tenant_id, triggered_at) WHERE status = 'unread';
      END IF;
    END $$;
    """,
    """
    DO $$ BEGIN
      IF to_regclass('public.event_outbox') IS NOT NULL THEN
        CREATE INDEX IF NOT EXISTS idx_event_outbox_pending ON event_outbox (created_at) WHERE status = 'PENDING';
        CREATE INDEX IF NOT EXISTS idx_event_outbox_tenant_created ON event_outbox (tenant_id, created_at);
      END IF;
    END $$;
    """,
]


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            for stmt in SQL_STATEMENTS:
                await conn.execute(text(stmt))
        print("migrate_constraints_v1: done")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
