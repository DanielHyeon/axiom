"""시나리오 저장소 — What-if 시나리오 CRUD.

Redis 기반 영속화로 시나리오를 저장/조회/삭제한다.
KAIR의 시나리오 저장/비교/재실행 기능을 Axiom 패턴으로 이식.
"""
from __future__ import annotations

import json
import re
from datetime import datetime

import structlog

logger = structlog.get_logger(__name__)

# Redis 키 접두사
_PREFIX = "axiom:vision:scenarios"


def _sanitize_key(part: str) -> str:
    """Redis 키 인젝션 방지를 위해 허용 문자만 남긴다."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "", part)


def _scenario_key(tenant_id: str, scenario_id: str) -> str:
    """개별 시나리오 Redis 키를 생성한다."""
    return f"{_PREFIX}:{_sanitize_key(tenant_id)}:{_sanitize_key(scenario_id)}"


def _list_key(tenant_id: str) -> str:
    """테넌트별 시나리오 인덱스 Redis 키를 생성한다."""
    return f"{_PREFIX}:{_sanitize_key(tenant_id)}:_index"


async def save_scenario(
    redis_client,
    tenant_id: str,
    scenario: dict,
    ttl_seconds: int = 86400 * 30,  # 30일 보관
) -> str:
    """시나리오를 Redis에 저장한다.

    Args:
        redis_client: aioredis 클라이언트 (None이면 조용히 실패)
        tenant_id: 테넌트 ID
        scenario: 시나리오 딕셔너리
        ttl_seconds: TTL (기본 30일)

    Returns:
        저장된 시나리오 ID
    """
    if redis_client is None:
        logger.warning("scenario_save_skipped", reason="redis_client is None")
        return scenario.get("id", "")

    scenario_id = scenario.get("id", "")
    if not scenario_id:
        from uuid import uuid4
        scenario_id = str(uuid4())
        scenario["id"] = scenario_id

    scenario["saved_at"] = datetime.utcnow().isoformat()
    scenario["tenant_id"] = tenant_id

    key = _scenario_key(tenant_id, scenario_id)
    await redis_client.set(key, json.dumps(scenario, default=str), ex=ttl_seconds)

    # 인덱스에 추가
    index_key = _list_key(tenant_id)
    await redis_client.sadd(index_key, scenario_id)
    await redis_client.expire(index_key, ttl_seconds)

    logger.info("scenario_saved", tenant_id=tenant_id, scenario_id=scenario_id)
    return scenario_id


async def load_scenario(
    redis_client,
    tenant_id: str,
    scenario_id: str,
) -> dict | None:
    """저장된 시나리오를 로드한다.

    Redis 클라이언트가 없거나 키가 없으면 None을 반환한다.
    """
    if redis_client is None:
        logger.warning("scenario_load_skipped", reason="redis_client is None")
        return None

    key = _scenario_key(tenant_id, scenario_id)
    raw = await redis_client.get(key)
    if not raw:
        return None
    return json.loads(raw)


async def list_scenarios(
    redis_client,
    tenant_id: str,
) -> list[dict]:
    """테넌트의 저장된 시나리오 목록을 조회한다.

    각 시나리오의 요약 정보(id, name, saved_at 등)만 반환한다.
    Redis 클라이언트가 없으면 빈 리스트를 반환한다.
    """
    if redis_client is None:
        logger.warning("scenario_list_skipped", reason="redis_client is None")
        return []

    index_key = _list_key(tenant_id)
    ids = await redis_client.smembers(index_key)
    if not ids:
        return []

    summaries: list[dict] = []
    for sid in ids:
        # Redis에서 bytes로 올 수 있음
        sid_str = sid.decode() if isinstance(sid, bytes) else str(sid)
        scenario = await load_scenario(redis_client, tenant_id, sid_str)
        if scenario:
            summaries.append({
                "id": scenario.get("id"),
                "name": scenario.get("name", ""),
                "description": scenario.get("description", ""),
                "interventions": scenario.get("interventions", {}),
                "saved_at": scenario.get("saved_at", ""),
            })

    # 최신순 정렬
    return sorted(summaries, key=lambda s: s.get("saved_at", ""), reverse=True)


async def delete_scenario(
    redis_client,
    tenant_id: str,
    scenario_id: str,
) -> bool:
    """시나리오를 삭제한다.

    Redis 클라이언트가 없으면 False를 반환한다.
    """
    if redis_client is None:
        logger.warning("scenario_delete_skipped", reason="redis_client is None")
        return False

    key = _scenario_key(tenant_id, scenario_id)
    deleted = await redis_client.delete(key)

    # 인덱스에서도 제거
    index_key = _list_key(tenant_id)
    await redis_client.srem(index_key, scenario_id)

    logger.info("scenario_deleted", tenant_id=tenant_id, scenario_id=scenario_id)
    return deleted > 0
