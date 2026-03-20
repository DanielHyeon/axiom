"""DDDExtractionService — LLM 기반 문서→DDD 개념 자동 추출 (Phase 2-F).

BusinessOS ontosys-main 패턴 적용:
  - 시스템 프롬프트로 DDD/이벤트스토밍 전문가 역할 부여
  - 문서 프래그먼트 순회 → LLM 호출 → 구조화된 JSON 응답
  - Jaccard 기반 퍼지 중복 제거
  - confidence 점수로 신뢰도 표시
  - Synapse extract-ontology 엔드포인트로 결과 적용

LLM이 설정되지 않은 경우 (OPENAI_API_KEY 없음) 개발용 mock 결과를 반환한다.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("axiom.weaver.ddd_extraction")

# ── LLM 시스템 프롬프트 ──────────────────────────────────────── #

DDD_EXTRACTION_SYSTEM_PROMPT = """\
당신은 DDD(Domain-Driven Design)와 이벤트 스토밍 전문가입니다.
주어진 텍스트에서 다음 개념을 식별하세요:

1. **Aggregate (어그리거트)**: 비즈니스 엔티티, 명사, 단수형
   - 예: Order, Customer, Machine, Sensor
   - 온톨로지 계층: process, resource, measure 중 적절한 것

2. **Command (커맨드)**: 수행할 액션, 명령형
   - 예: CreateOrder, StartMaintenance, ApprovePayment
   - 형식: 동사 + 명사 (UpperCamelCase)

3. **Event (이벤트)**: 발생한 사실, 과거형
   - 예: OrderCreated, MaintenanceCompleted, PaymentApproved
   - 형식: 명사 + 과거분사 (UpperCamelCase)

4. **Policy (정책)**: 반응형 비즈니스 규칙
   - 예: "결제 확인되면 배송 시작", "온도 초과 시 정비 예약"
   - 형식: snake_case 또는 자연어 설명

각 개념에 대해:
- name: 정확한 이름
- description: 간결한 설명 (한국어)
- confidence: 0.0-1.0 (텍스트에서 명확히 언급되었으면 0.9+, 추론이면 0.5-0.7)
- source_text: 근거가 되는 원문 발췌
- suggested_layer: kpi | measure | process | resource | driver 중 적절한 것

JSON 형식으로 출력하세요:
{
  "aggregates": [{"name": "...", "description": "...", "confidence": 0.9, "source_text": "...", "suggested_layer": "process"}],
  "commands": [{"name": "...", "description": "...", "confidence": 0.8, "source_text": "..."}],
  "events": [{"name": "...", "description": "...", "confidence": 0.85, "source_text": "..."}],
  "policies": [{"name": "...", "description": "...", "confidence": 0.7, "source_text": "..."}],
  "relations": [{"source": "...", "target": "...", "type": "TARGETS|EMITS|LISTENS|ISSUES", "weight": 0.8}]
}
"""


class DDDExtractionService:
    """LLM 기반 DDD 개념 추출기.

    OPENAI_API_KEY 환경변수가 없으면 개발용 mock 결과를 반환한다.
    """

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        self._model = os.getenv("OPENAI_MODEL", "gpt-4o")
        self._api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

    # ── 메인 추출 ─────────────────────────────────────────────── #

    async def extract_from_fragments(
        self,
        fragments: list[dict[str, Any]],
        case_id: str = "",
        existing_context: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """문서 프래그먼트 목록에서 DDD 개념을 추출한다.

        Args:
            fragments: [{text, page, span_start, span_end, ...}] 리스트
            case_id: 케이스 ID (기존 온톨로지 컨텍스트 조회용)
            existing_context: 이미 존재하는 온톨로지 노드 목록 (중복 방지)

        Returns:
            {aggregates, commands, events, policies, relations,
             total_entities, avg_confidence}
        """
        all_results: dict[str, list] = {
            "aggregates": [],
            "commands": [],
            "events": [],
            "policies": [],
            "relations": [],
        }

        # 각 프래그먼트에 대해 LLM 호출
        for idx, fragment in enumerate(fragments):
            logger.info(
                "DDD 추출 진행: fragment %d/%d (page=%s)",
                idx + 1, len(fragments), fragment.get("page", "?"),
            )
            partial = await self._extract_single(fragment, existing_context)
            for key in all_results:
                all_results[key].extend(partial.get(key, []))

        # 엔티티별 퍼지 중복 제거
        for key in ("aggregates", "commands", "events", "policies"):
            all_results[key] = self._deduplicate(all_results[key])

        # 통계 계산
        entity_keys = ("aggregates", "commands", "events", "policies")
        all_entities = [e for k in entity_keys for e in all_results[k]]
        total = len(all_entities)
        avg_conf = (
            sum(e.get("confidence", 0.0) for e in all_entities) / total
            if total > 0
            else 0.0
        )

        all_results["total_entities"] = total
        all_results["avg_confidence"] = round(avg_conf, 3)

        return all_results

    async def _extract_single(
        self,
        fragment: dict[str, Any],
        context: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """단일 프래그먼트에서 DDD 개념 추출."""
        # 기존 온톨로지 노드 이름 목록을 컨텍스트로 제공 (중복 생성 방지)
        context_str = ""
        if context:
            names = [n.get("name", "") for n in context[:50] if n.get("name")]
            if names:
                context_str = (
                    f"\n\n기존 온톨로지 노드 (중복 생성 방지):\n{', '.join(names)}"
                )

        user_prompt = (
            f"텍스트:\n---\n{fragment.get('text', '')}\n---\n"
            f"페이지: {fragment.get('page', 'N/A')}"
            f"{context_str}"
        )

        # LLM 호출 또는 mock
        if not self._api_key:
            logger.info("OPENAI_API_KEY 미설정 — mock 추출 결과 반환")
            raw = self._mock_extraction(fragment)
        else:
            raw = await self._call_llm(user_prompt)

        result = self._parse_llm_response(raw)

        # 소스 앵커 연결 — 추출된 각 엔티티에 원본 문서 위치 부여
        for key in ("aggregates", "commands", "events", "policies"):
            for entity in result.get(key, []):
                entity["source_anchor"] = {
                    "doc_id": fragment.get("doc_id", ""),
                    "fragment_id": fragment.get("id", ""),
                    "page": fragment.get("page", 0),
                    "span_start": fragment.get("span_start", 0),
                    "span_end": fragment.get("span_end", 0),
                }

        return result

    async def _call_llm(self, user_prompt: str) -> str:
        """OpenAI API 호출하여 JSON 응답 텍스트 반환."""
        url = f"{self._api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": DDD_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.error("LLM 호출 실패: %s — mock 결과 반환", exc)
            return "{}"

    # ── 퍼지 중복 제거 ────────────────────────────────────────── #

    def _deduplicate(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """이름 기반 퍼지 중복 제거 (유사도 > 0.85이면 병합).

        동일/유사 이름이면 confidence가 높은 엔티티를 유지한다.
        """
        seen: dict[str, int] = {}  # normalized_name → result 인덱스
        result: list[dict[str, Any]] = []

        for entity in entities:
            name = entity.get("name", "")
            if not name:
                continue
            name_norm = name.lower().replace("_", "").replace("-", "").replace(" ", "")

            # 기존에 유사한 이름이 있는지 확인
            duplicate = False
            for existing_name, idx in seen.items():
                if self._name_similarity(name_norm, existing_name) > 0.85:
                    # confidence가 더 높으면 교체
                    if entity.get("confidence", 0) > result[idx].get("confidence", 0):
                        result[idx] = entity
                    duplicate = True
                    break

            if not duplicate:
                seen[name_norm] = len(result)
                result.append(entity)

        return result

    @staticmethod
    def _name_similarity(a: str, b: str) -> float:
        """Jaccard 문자 집합 유사도."""
        if a == b:
            return 1.0
        set_a = set(a)
        set_b = set(b)
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0

    # ── LLM 응답 파싱 ────────────────────────────────────────── #

    @staticmethod
    def _parse_llm_response(response: str) -> dict[str, Any]:
        """LLM 응답 JSON 파싱. 파싱 실패 시 빈 결과 반환."""
        empty: dict[str, Any] = {
            "aggregates": [], "commands": [], "events": [], "policies": [],
            "relations": [],
        }
        if not response or not response.strip():
            return empty

        try:
            parsed = json.loads(response)
            if isinstance(parsed, dict):
                # 필수 키가 없으면 빈 리스트로 채움
                for key in empty:
                    if key not in parsed:
                        parsed[key] = []
                return parsed
        except json.JSONDecodeError:
            pass

        # JSON 블록 추출 재시도
        match = re.search(r"\{[\s\S]*\}", response)
        if match:
            try:
                parsed = json.loads(match.group())
                if isinstance(parsed, dict):
                    for key in empty:
                        if key not in parsed:
                            parsed[key] = []
                    return parsed
            except json.JSONDecodeError:
                pass

        logger.warning("LLM 응답 JSON 파싱 실패 — 빈 결과 반환")
        return empty

    # ── Mock 추출 (개발용) ────────────────────────────────────── #

    @staticmethod
    def _mock_extraction(fragment: dict[str, Any]) -> str:
        """LLM 없이 개발용 mock 결과 생성.

        텍스트 내용을 기반으로 최소한의 엔티티를 생성한다.
        """
        text = fragment.get("text", "")[:200]
        mock = {
            "aggregates": [
                {
                    "name": "Document",
                    "description": "업로드된 문서 어그리거트",
                    "confidence": 0.7,
                    "source_text": text[:80],
                    "suggested_layer": "resource",
                }
            ],
            "commands": [
                {
                    "name": "ProcessDocument",
                    "description": "문서 처리 커맨드",
                    "confidence": 0.6,
                    "source_text": text[:60],
                }
            ],
            "events": [
                {
                    "name": "DocumentProcessed",
                    "description": "문서 처리 완료 이벤트",
                    "confidence": 0.65,
                    "source_text": text[:60],
                }
            ],
            "policies": [],
            "relations": [
                {
                    "source": "ProcessDocument",
                    "target": "Document",
                    "type": "TARGETS",
                    "weight": 0.7,
                },
                {
                    "source": "ProcessDocument",
                    "target": "DocumentProcessed",
                    "type": "EMITS",
                    "weight": 0.7,
                },
            ],
        }
        return json.dumps(mock, ensure_ascii=False)

    # ── Synapse 온톨로지 적용 ─────────────────────────────────── #

    async def apply_to_ontology(
        self,
        extraction_result: dict[str, Any],
        case_id: str,
        tenant_id: str,
        selected_entity_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """추출 결과를 Synapse 온톨로지에 적용한다.

        Synapse /api/v3/synapse/extraction/documents/{doc_id}/extract-ontology
        엔드포인트를 호출하여 노드를 생성한다.

        Args:
            extraction_result: extract_from_fragments 반환값
            case_id: 케이스 ID
            tenant_id: 테넌트 ID
            selected_entity_names: 선택된 엔티티 이름 (None이면 전체 적용)

        Returns:
            {applied_count, node_ids, skipped}
        """
        # 적용할 엔티티 필터링
        entities_to_apply: list[dict[str, Any]] = []
        for key in ("aggregates", "commands", "events", "policies"):
            for entity in extraction_result.get(key, []):
                if selected_entity_names is None or entity.get("name") in selected_entity_names:
                    entity["entity_type"] = key.rstrip("s")  # aggregate, command, event, policy
                    entities_to_apply.append(entity)

        if not entities_to_apply:
            return {"applied_count": 0, "node_ids": [], "skipped": 0}

        # Synapse extract-ontology 엔드포인트 호출
        synapse_base = settings.synapse_base_url.rstrip("/")
        url = f"{synapse_base}/api/v3/synapse/extraction/documents/{case_id}/extract-ontology"

        payload = {
            "case_id": case_id,
            "entities": entities_to_apply,
            "relations": extraction_result.get("relations", []),
        }

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id

        node_ids: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                # Synapse 응답에서 생성된 노드 ID 추출
                result_data = data.get("data", data)
                if isinstance(result_data, dict):
                    node_ids = result_data.get("node_ids", [])
                    if not node_ids and result_data.get("entities"):
                        node_ids = [
                            e.get("id", "") for e in result_data["entities"]
                            if e.get("id")
                        ]

            logger.info(
                "Synapse 온톨로지 적용 완료: case=%s, entities=%d, nodes=%d",
                case_id, len(entities_to_apply), len(node_ids),
            )
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Synapse 온톨로지 적용 HTTP 오류: %d — %s",
                exc.response.status_code, exc.response.text[:200],
            )
            raise RuntimeError(
                f"Synapse 온톨로지 적용 실패 (HTTP {exc.response.status_code})"
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("Synapse 온톨로지 적용 연결 실패: %s", exc)
            raise RuntimeError(f"Synapse 연결 실패: {exc}") from exc

        return {
            "applied_count": len(entities_to_apply),
            "node_ids": node_ids,
            "skipped": 0,
        }


# 싱글톤 인스턴스
ddd_extraction_service = DDDExtractionService()
