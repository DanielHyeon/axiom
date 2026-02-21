import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.database import AsyncSessionLocal, engine
from app.models.base_models import Base


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    if engine.url.get_backend_name() != "postgresql":
        pytest.skip("postgres-only constraint test")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_process_watch_constraint_and_index_contracts():
    expected_constraints = {
        "uq_bpm_process_definition_tenant_name_version",
        "uq_bpm_process_role_binding_proc_role_tenant",
        "uq_watch_subscriptions_user_evt_case_tenant_active",
        "uq_watch_rules_tenant_name_event",
    }
    expected_indexes = {
        "idx_bpm_work_item_tenant_proc_status",
        "idx_bpm_work_item_tenant_assignee_status",
        "idx_watch_alerts_tenant_status_triggered",
        "idx_event_outbox_pending",
    }

    async with AsyncSessionLocal() as session:
        cons = await session.execute(
            text(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conname = ANY(:names)
                """
            ),
            {"names": list(expected_constraints)},
        )
        found_cons = {row[0] for row in cons.fetchall()}
        assert expected_constraints.issubset(found_cons)

        idx = await session.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = ANY(:names)
                """
            ),
            {"names": list(expected_indexes)},
        )
        found_idx = {row[0] for row in idx.fetchall()}
        assert expected_indexes.issubset(found_idx)


@pytest.mark.asyncio
async def test_watch_rule_unique_constraint_enforced():
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                """
                INSERT INTO watch_rules (id, name, event_type, definition, active, tenant_id)
                VALUES
                ('wr-1', 'same-name', 'deadline', '{}'::jsonb, true, 'tenant-1')
                """
            )
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        with pytest.raises(Exception):
            await session.execute(
                text(
                    """
                    INSERT INTO watch_rules (id, name, event_type, definition, active, tenant_id)
                    VALUES
                    ('wr-2', 'same-name', 'deadline', '{}'::jsonb, true, 'tenant-1')
                    """
                )
            )
            await session.commit()
        await session.rollback()
