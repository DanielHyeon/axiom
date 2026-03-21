"""LLM 응답 시맨틱 캐시 -- Redis 기반 프롬프트 중복 제거.

KAIR의 llm_cache.py를 참조하여 Axiom Oracle 패턴으로 이식.

기능:
  - 프롬프트 해시 기반 정확 매칭 (빠른 조회)
  - TTL 기반 자동 만료
  - 캐시 적중/미적중 메트릭 추적
  - 히트율 통계 제공
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Redis 키 접두사
_CACHE_PREFIX = "axiom:oracle:llm-cache"
_METRICS_KEY = "axiom:oracle:llm-cache:metrics"

# 기본 TTL (1시간)
DEFAULT_TTL = 3600


def _make_cache_key(prompt: str, model: str = "", system: str = "", tenant_id: str = "") -> str:
    """프롬프트 + 모델 + 시스템 프롬프트 + 테넌트를 조합한 캐시 키를 생성한다.

    SHA-256 해시로 고정 길이 키를 만들고, tenant_id를 키 접두사에 포함하여
    테넌트 간 캐시 격리를 보장한다.
    """
    raw = f"{tenant_id}::{model}::{system}::{prompt}"
    hash_val = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{_CACHE_PREFIX}:{tenant_id}:{hash_val}"


async def get_cached_response(
    redis_client: Any,
    prompt: str,
    model: str = "",
    system: str = "",
    tenant_id: str = "",
) -> str | None:
    """캐시에서 LLM 응답을 조회한다.

    Args:
        redis_client: Redis 비동기 클라이언트
        prompt: 조회할 프롬프트
        model: LLM 모델명
        system: 시스템 프롬프트
        tenant_id: 테넌트 ID (멀티테넌트 캐시 격리)

    Returns:
        캐시 적중 시 응답 문자열, 미적중 시 None
    """
    if redis_client is None:
        return None

    key = _make_cache_key(prompt, model, system, tenant_id)
    try:
        cached = await redis_client.get(key)
        if cached:
            # 메트릭: 적중
            await _increment_metric(redis_client, "hits")
            raw = cached.decode() if isinstance(cached, bytes) else str(cached)
            data = json.loads(raw)
            logger.debug("llm_cache_hit", key_prefix=key[:40])
            return data.get("response", "")
        else:
            # 메트릭: 미적중
            await _increment_metric(redis_client, "misses")
            return None
    except Exception as e:
        logger.warning("llm_cache_get_error", error=str(e))
        return None


async def set_cached_response(
    redis_client: Any,
    prompt: str,
    response: str,
    model: str = "",
    system: str = "",
    ttl: int = DEFAULT_TTL,
    tenant_id: str = "",
) -> bool:
    """LLM 응답을 캐시에 저장한다."""
    if redis_client is None:
        return False

    key = _make_cache_key(prompt, model, system, tenant_id)
    try:
        data = {
            "response": response,
            "model": model,
            "cached_at": time.time(),
            "prompt_preview": prompt[:200],
        }
        await redis_client.set(key, json.dumps(data), ex=ttl)
        await _increment_metric(redis_client, "sets")
        logger.debug("llm_cache_set", key_prefix=key[:40], ttl=ttl)
        return True
    except Exception as e:
        logger.warning("llm_cache_set_error", error=str(e))
        return False


async def get_cache_metrics(redis_client: Any) -> dict[str, Any]:
    """캐시 적중/미적중 통계를 조회한다."""
    if redis_client is None:
        return {"hits": 0, "misses": 0, "sets": 0, "hit_rate": 0.0}

    try:
        raw = await redis_client.hgetall(_METRICS_KEY)
        # redis.asyncio는 decode_responses=False일 때 bytes 키를 반환함
        hits = int(raw.get(b"hits", raw.get("hits", 0)))
        misses = int(raw.get(b"misses", raw.get("misses", 0)))
        sets = int(raw.get(b"sets", raw.get("sets", 0)))
        total = hits + misses
        hit_rate = round(hits / total * 100, 2) if total > 0 else 0.0
        return {"hits": hits, "misses": misses, "sets": sets, "hit_rate": hit_rate}
    except Exception:
        return {"hits": 0, "misses": 0, "sets": 0, "hit_rate": 0.0}


async def invalidate_cache(
    redis_client: Any,
    prompt: str,
    model: str = "",
    system: str = "",
    tenant_id: str = "",
) -> bool:
    """특정 캐시 항목을 무효화한다."""
    if redis_client is None:
        return False
    key = _make_cache_key(prompt, model, system, tenant_id)
    try:
        await redis_client.delete(key)
        return True
    except Exception:
        return False


async def _increment_metric(redis_client: Any, field: str) -> None:
    """메트릭 카운터를 증가시킨다."""
    try:
        await redis_client.hincrby(_METRICS_KEY, field, 1)
    except Exception:
        pass


# ── Phase 2: 시맨틱 캐시 통합 조회 ────────────────────────────────


async def get_cached_response_with_semantic(
    redis_client: Any,
    prompt: str,
    model: str = "",
    system: str = "",
    api_key: str = "",
    similarity_threshold: float = 0.92,
    tenant_id: str = "",
    project_id: str = "",
) -> tuple[str | None, str]:
    """Phase 1 해시 + Phase 2 시맨틱 통합 캐시 조회.

    2단계 전략으로 캐시를 조회한다:
      1단계: 해시 정확 매칭 (Phase 1) — 프롬프트가 완전히 동일할 때 즉시 반환
      2단계: 임베딩 유사도 매칭 (Phase 2) — 의미적으로 유사한 프롬프트 탐색

    Phase 2는 OpenAI API 키가 있고 numpy가 설치된 경우에만 동작한다.
    API 키가 없으면 Phase 1만 사용한다.

    Args:
        redis_client: Redis 비동기 클라이언트
        prompt: 조회할 프롬프트
        model: LLM 모델명 (Phase 1 해시에 포함)
        system: 시스템 프롬프트 (Phase 1 해시에 포함)
        api_key: OpenAI API 키 (Phase 2 임베딩용)
        similarity_threshold: 시맨틱 매칭 임계값 (기본 0.92)
        tenant_id: 테넌트 ID (멀티테넌트 캐시 격리)
        project_id: 프로젝트 ID (프로젝트 캐시 격리)

    Returns:
        (응답 | None, 매칭 방법: "hash" | "semantic" | "miss")
    """
    # Phase 1: 해시 정확 매칭 (빠름 — 추가 API 호출 없음)
    exact = await get_cached_response(redis_client, prompt, model, system, tenant_id=tenant_id)
    if exact is not None:
        return exact, "hash"

    # Phase 2: 시맨틱 유사도 매칭 (느림 — 임베딩 API 호출 필요)
    try:
        from app.services.embedding_cache import semantic_cache_get
    except ImportError:
        logger.debug("embedding_cache_module_unavailable")
        return None, "miss"

    semantic_result, score = await semantic_cache_get(
        redis_client, prompt, api_key, similarity_threshold,
        tenant_id=tenant_id, project_id=project_id,
    )
    if semantic_result is not None:
        # 시맨틱 적중도 메트릭에 기록
        await _increment_metric(redis_client, "semantic_hits")
        return semantic_result, "semantic"

    return None, "miss"
