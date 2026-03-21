"""임베딩 기반 시맨틱 캐시 — 유사 프롬프트 매칭.

Phase 1의 해시 기반 정확 매칭에 추가하여,
코사인 유사도 기반으로 의미적으로 유사한 프롬프트의 캐시를 재활용한다.

전략:
  1단계: 해시 정확 매칭 (Phase 1 — 즉시 반환)
  2단계: 임베딩 유사도 매칭 (Phase 2 — 유사도 >= threshold 시 반환)

임베딩은 OpenAI text-embedding-3-small 모델을 사용하되,
API 키가 없으면 Phase 1만 동작한다.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# numpy는 선택적 의존성 — 없으면 시맨틱 캐시 비활성화
try:
    import numpy as np

    _HAS_NUMPY = True
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]
    _HAS_NUMPY = False
    logger.info("numpy_not_available", msg="시맨틱 캐시 비활성화 (numpy 미설치)")

# Redis 키 접두사
_EMBED_PREFIX = "axiom:oracle:embed-cache"
_EMBED_INDEX_KEY = "axiom:oracle:embed-cache:index"

# 유사도 임계값 — 이 값 이상이면 캐시 적중으로 판정
DEFAULT_SIMILARITY_THRESHOLD = 0.92


def _embed_key(tenant_id: str, project_id: str, prompt_hash: str) -> str:
    """테넌트/프로젝트 격리된 임베딩 캐시 키를 생성한다."""
    return f"{_EMBED_PREFIX}:{tenant_id}:{project_id}:{prompt_hash}"


def _embed_index_key(tenant_id: str, project_id: str) -> str:
    """테넌트/프로젝트 격리된 임베딩 인덱스 키를 생성한다."""
    return f"{_EMBED_INDEX_KEY}:{tenant_id}:{project_id}"

# 임베딩 차원 (text-embedding-3-small)
EMBEDDING_DIM = 1536


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """코사인 유사도를 계산한다.

    두 벡터 간의 코사인 각도를 통해 의미적 유사도를 측정한다.
    값이 1.0에 가까울수록 의미가 유사하다.
    """
    if not _HAS_NUMPY:
        return 0.0

    va = np.array(a)
    vb = np.array(b)
    dot = float(np.dot(va, vb))
    norm_a = float(np.linalg.norm(va))
    norm_b = float(np.linalg.norm(vb))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _get_embedding(
    text: str,
    api_key: str,
    model: str = "text-embedding-3-small",
) -> list[float] | None:
    """OpenAI 임베딩 API를 호출한다.

    텍스트를 고차원 벡터로 변환하여 의미적 비교를 가능하게 한다.
    API 키가 없거나 openai 패키지가 없으면 None을 반환한다.
    """
    if not api_key:
        return None
    try:
        from openai import AsyncOpenAI  # 선택적 의존성

        client = AsyncOpenAI(api_key=api_key)
        # 임베딩 모델 입력 최대 길이 제한 (8000자)
        response = await client.embeddings.create(
            input=text[:8000],
            model=model,
        )
        return response.data[0].embedding
    except ImportError:
        logger.warning("openai_not_installed", msg="openai 패키지 미설치 — 임베딩 생성 불가")
        return None
    except Exception as e:
        logger.warning("embedding_api_failed", error=str(e))
        return None


async def semantic_cache_get(
    redis_client: Any,
    prompt: str,
    api_key: str = "",
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    tenant_id: str = "",
    project_id: str = "",
) -> tuple[str | None, float]:
    """시맨틱 캐시에서 유사 프롬프트를 검색한다.

    모든 캐시된 임베딩과 현재 프롬프트 임베딩 간의 코사인 유사도를 계산하고,
    임계값 이상인 가장 유사한 응답을 반환한다.

    Args:
        redis_client: Redis 비동기 클라이언트
        prompt: 검색할 프롬프트
        api_key: OpenAI API 키 (없으면 비활성화)
        similarity_threshold: 캐시 적중 판정 임계값 (기본 0.92)
        tenant_id: 테넌트 ID (멀티테넌트 격리)
        project_id: 프로젝트 ID (프로젝트 격리)

    Returns:
        (캐시된 응답 | None, 최고 유사도 점수)
    """
    if redis_client is None or not api_key or not _HAS_NUMPY:
        return None, 0.0

    # 현재 프롬프트의 임베딩 생성
    query_embed = await _get_embedding(prompt, api_key)
    if query_embed is None:
        return None, 0.0

    try:
        # 테넌트/프로젝트 격리된 인덱스에서 캐시 키 조회
        index_key = _embed_index_key(tenant_id, project_id)
        keys = await redis_client.smembers(index_key)
        if not keys:
            return None, 0.0

        best_score = 0.0
        best_response = None

        for key_bytes in keys:
            key = key_bytes.decode() if isinstance(key_bytes, bytes) else str(key_bytes)
            raw = await redis_client.get(key)
            if not raw:
                # 만료된 키 — 인덱스에서 정리
                await redis_client.srem(index_key, key)
                continue

            data = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            cached_embed = data.get("embedding")
            if not cached_embed:
                continue

            score = _cosine_similarity(query_embed, cached_embed)
            if score > best_score:
                best_score = score
                if score >= similarity_threshold:
                    best_response = data.get("response", "")

        if best_response is not None:
            logger.info(
                "semantic_cache_hit",
                similarity=round(best_score, 4),
                threshold=similarity_threshold,
            )
            return best_response, best_score
        else:
            logger.debug(
                "semantic_cache_miss",
                best_similarity=round(best_score, 4),
                threshold=similarity_threshold,
            )
            return None, best_score

    except Exception as e:
        logger.warning("semantic_cache_get_error", error=str(e))
        return None, 0.0


async def semantic_cache_set(
    redis_client: Any,
    prompt: str,
    response: str,
    api_key: str = "",
    ttl: int = 3600,
    tenant_id: str = "",
    project_id: str = "",
) -> bool:
    """시맨틱 캐시에 응답을 저장한다 (임베딩 포함).

    프롬프트의 임베딩을 생성하고 응답과 함께 Redis에 저장한다.
    인덱스 셋에 키를 추가하여 나중에 검색할 수 있게 한다.

    Args:
        redis_client: Redis 비동기 클라이언트
        prompt: 캐시할 프롬프트
        response: 캐시할 LLM 응답
        api_key: OpenAI API 키
        ttl: 캐시 유효기간 (초, 기본 1시간)
        tenant_id: 테넌트 ID (멀티테넌트 격리)
        project_id: 프로젝트 ID (프로젝트 격리)

    Returns:
        저장 성공 여부
    """
    if redis_client is None or not api_key or not _HAS_NUMPY:
        return False

    embed = await _get_embedding(prompt, api_key)
    if embed is None:
        return False

    try:
        # 프롬프트 해시로 테넌트/프로젝트 격리된 고유 키 생성
        key_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        key = _embed_key(tenant_id, project_id, key_hash)

        data = {
            "response": response,
            "embedding": embed,
            "prompt_preview": prompt[:200],
            "cached_at": time.time(),
        }
        await redis_client.set(key, json.dumps(data), ex=ttl)
        # 테넌트/프로젝트 격리된 인덱스에 키 등록 (검색 시 순회용)
        index_key = _embed_index_key(tenant_id, project_id)
        await redis_client.sadd(index_key, key)
        await redis_client.expire(index_key, ttl)

        logger.debug("semantic_cache_set", key=key[:40])
        return True

    except Exception as e:
        logger.warning("semantic_cache_set_error", error=str(e))
        return False
