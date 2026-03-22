"""쿼리 유사도 클러스터링 서비스.

실행된 쿼리를 임베딩 벡터로 변환하고, 기존 쿼리와의 유사도를 계산하여
유사한 쿼리끼리 canonical_id로 그룹화한다.

이점:
- 동일 의도의 쿼리가 같은 캐시 항목을 공유하여 캐시 적중률 향상
- 피드백이 canonical 그룹 전체에 적용되어 학습 효율 증가
"""
from __future__ import annotations

import math
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


# ── 유사도 임계값 ──────────────────────────────────────────────────
# HIGH: 거의 동일한 질문 — 같은 canonical 그룹으로 묶는다
HIGH_THRESHOLD: float = settings.QUERY_SIMILARITY_HIGH_THRESHOLD
# MID: 관련 있는 질문 — 로그에 참고용으로 기록하지만 그룹화하지 않는다
MID_THRESHOLD: float = settings.QUERY_SIMILARITY_MID_THRESHOLD
# 인메모리 스토어 최대 크기 — 초과 시 가장 오래된 항목부터 제거
MAX_STORE_SIZE: int = settings.QUERY_SIMILARITY_MAX_STORE


@dataclass
class SimilarQuery:
    """유사 쿼리 검색 결과를 담는 데이터 클래스."""

    query_id: str          # 원본 쿼리 ID
    question: str          # 원본 자연어 질문
    sql: str               # 원본 SQL
    similarity_score: float  # 코사인 유사도 (0.0 ~ 1.0)
    canonical_id: str      # 이 쿼리가 속한 클러스터의 대표 ID


@dataclass
class _StoredEntry:
    """인메모리 스토어에 저장되는 쿼리 항목."""

    query_id: str
    question: str
    sql: str
    embedding: list[float]
    canonical_id: str


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """두 벡터 간의 코사인 유사도를 계산한다.

    numpy 의존성 없이 순수 파이썬으로 구현하여
    외부 패키지 설치 부담을 줄인다.

    Args:
        a: 첫 번째 벡터
        b: 두 번째 벡터

    Returns:
        코사인 유사도 (0.0 ~ 1.0). 벡터 길이가 다르거나 노름이 0이면 0.0 반환
    """
    if len(a) != len(b) or len(a) == 0:
        return 0.0

    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


class QuerySimilarityService:
    """쿼리 유사도 클러스터링 서비스.

    인메모리 OrderedDict로 쿼리 임베딩을 관리하며,
    새 쿼리가 들어올 때 기존 쿼리와의 유사도를 비교하여
    canonical_id로 그룹화한다.

    사용 예시:
        svc = QuerySimilarityService(embed_fn=my_embed_fn)
        canonical = await svc.cluster("매출 합계를 보여줘", "SELECT SUM(revenue)...", "q-1")
    """

    def __init__(
        self,
        *,
        embed_fn: Any | None = None,
        high_threshold: float | None = None,
        mid_threshold: float | None = None,
        max_store: int | None = None,
    ) -> None:
        """서비스를 초기화한다.

        Args:
            embed_fn: 텍스트를 임베딩 벡터로 변환하는 비동기 함수.
                      시그니처: async (text: str) -> list[float] | None
                      None이면 간단한 해시 기반 폴백을 사용한다.
            high_threshold: 클러스터 그룹화 임계값 (기본 0.95)
            mid_threshold: 소프트 매칭 로그 임계값 (기본 0.80)
            max_store: 인메모리 스토어 최대 크기 (기본 10000)
        """
        self._embed_fn = embed_fn
        self._high_threshold = high_threshold if high_threshold is not None else HIGH_THRESHOLD
        self._mid_threshold = mid_threshold if mid_threshold is not None else MID_THRESHOLD
        self._max_store = max_store if max_store is not None else MAX_STORE_SIZE

        # OrderedDict로 삽입 순서를 유지하여 FIFO 퇴출 구현
        self._store: OrderedDict[str, _StoredEntry] = OrderedDict()

    @property
    def store_size(self) -> int:
        """현재 스토어에 저장된 쿼리 수를 반환한다."""
        return len(self._store)

    async def _get_embedding(self, text: str) -> list[float] | None:
        """텍스트의 임베딩 벡터를 생성한다.

        외부 embed_fn이 제공되면 사용하고, 없으면 None을 반환한다.
        """
        if self._embed_fn is None:
            return None

        try:
            result = await self._embed_fn(text)
            return result
        except Exception as exc:
            logger.warning("query_similarity_embed_failed", error=str(exc))
            return None

    async def find_similar(
        self,
        question: str,
        threshold: float | None = None,
    ) -> SimilarQuery | None:
        """기존 쿼리 중 가장 유사한 것을 찾는다.

        임베딩 벡터 간 코사인 유사도를 계산하고,
        임계값 이상인 쿼리 중 가장 유사도가 높은 것을 반환한다.

        Args:
            question: 검색할 자연어 질문
            threshold: 유사도 임계값 (기본: high_threshold = 0.95)

        Returns:
            가장 유사한 쿼리 정보 또는 None (임계값 미달 시)
        """
        if not settings.ENABLE_QUERY_SIMILARITY:
            return None

        effective_threshold = threshold if threshold is not None else self._high_threshold

        # 임베딩 생성
        query_embed = await self._get_embedding(question)
        if query_embed is None:
            logger.info("query_similarity_skip_no_embedding", question_preview=question[:50])
            return None

        # 스토어가 비어있으면 검색 불필요
        if not self._store:
            return None

        best_score = 0.0
        best_entry: _StoredEntry | None = None

        # 모든 저장된 쿼리와 유사도 비교
        for entry in self._store.values():
            score = _cosine_similarity(query_embed, entry.embedding)

            # MID 임계값 이상이면 로그 기록 (디버그용)
            if score >= self._mid_threshold and score > best_score:
                best_score = score
                best_entry = entry

        # HIGH 임계값 이상인 경우만 결과 반환
        if best_entry is not None and best_score >= effective_threshold:
            logger.info(
                "query_similarity_found",
                similarity=round(best_score, 4),
                canonical_id=best_entry.canonical_id,
                question_preview=question[:50],
            )
            return SimilarQuery(
                query_id=best_entry.query_id,
                question=best_entry.question,
                sql=best_entry.sql,
                similarity_score=best_score,
                canonical_id=best_entry.canonical_id,
            )

        # MID 이상이면 로그만 남기고 None 반환
        if best_entry is not None and best_score >= self._mid_threshold:
            logger.info(
                "query_similarity_soft_match",
                similarity=round(best_score, 4),
                threshold=effective_threshold,
                question_preview=question[:50],
            )

        return None

    async def cluster(
        self,
        question: str,
        sql: str,
        query_id: str,
    ) -> str:
        """쿼리를 클러스터에 등록하고 canonical_id를 반환한다.

        1) 기존 쿼리 중 HIGH 임계값 이상 유사한 것이 있으면
           해당 쿼리의 canonical_id를 재사용한다.
        2) 없으면 새로운 canonical_id를 생성한다.
        3) 쿼리를 인메모리 스토어에 저장한다.

        Args:
            question: 자연어 질문
            sql: 생성된 SQL
            query_id: 이 쿼리의 고유 ID

        Returns:
            canonical_id — 기존 클러스터 또는 새 클러스터의 대표 ID
        """
        if not settings.ENABLE_QUERY_SIMILARITY:
            # 비활성화 시 쿼리 ID 자체를 canonical_id로 사용
            return query_id

        # 임베딩 생성
        query_embed = await self._get_embedding(question)
        if query_embed is None:
            # 임베딩 실패 시 쿼리 ID 자체를 canonical_id로 사용
            logger.info("query_similarity_cluster_no_embedding", query_id=query_id)
            return query_id

        # 유사한 기존 쿼리 검색
        similar = await self.find_similar(question)
        if similar is not None:
            canonical_id = similar.canonical_id
            logger.info(
                "query_similarity_cluster_reuse",
                query_id=query_id,
                canonical_id=canonical_id,
                similarity=round(similar.similarity_score, 4),
            )
        else:
            # 새 클러스터 생성 — canonical_id로 UUID 사용
            canonical_id = str(uuid.uuid4())
            logger.info(
                "query_similarity_cluster_new",
                query_id=query_id,
                canonical_id=canonical_id,
            )

        # 스토어 크기 제한 — 가장 오래된 항목부터 제거 (FIFO)
        while len(self._store) >= self._max_store:
            evicted_key, evicted = self._store.popitem(last=False)
            logger.info("query_similarity_store_evict", evicted_query_id=evicted_key)

        # 스토어에 저장
        self._store[query_id] = _StoredEntry(
            query_id=query_id,
            question=question,
            sql=sql,
            embedding=query_embed,
            canonical_id=canonical_id,
        )

        return canonical_id

    def get_cluster_members(self, canonical_id: str) -> list[dict[str, Any]]:
        """특정 canonical_id에 속한 모든 쿼리를 조회한다.

        Args:
            canonical_id: 클러스터 대표 ID

        Returns:
            클러스터에 속한 쿼리 정보 목록
        """
        members = []
        for entry in self._store.values():
            if entry.canonical_id == canonical_id:
                members.append({
                    "query_id": entry.query_id,
                    "question": entry.question,
                    "sql": entry.sql,
                })
        return members

    def clear(self) -> None:
        """인메모리 스토어를 초기화한다 (테스트용)."""
        self._store.clear()


# ── 모듈 수준 싱글턴 인스턴스 ──────────────────────────────────────
# embed_fn은 외부에서 설정해야 한다 (예: OpenAI API 연동 시)
query_similarity_service = QuerySimilarityService()
