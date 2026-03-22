"""레이어별 추출 품질 평가기 — 노드 수와 관계 밀도로 신뢰도를 계산한다.

신뢰도 공식:
  - 노드가 0개: 0.0 (추출 실패)
  - 노드가 1개: 0.4 (최소한의 결과)
  - 노드가 2~9개: 0.5 ~ 0.9 (선형 보간)
  - 노드가 10개 이상: 1.0 (충분한 추출)

관계가 있으면 보너스 +0.05 (최대 1.0)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.deep_agents.layer_agents import LayerSchema


@dataclass
class QualityResult:
    """레이어 품질 평가 결과."""

    confidence: float  # 0.0 ~ 1.0
    node_count: int  # 추출된 노드 수
    relation_count: int  # 추출된 관계 수
    missing_info: list[str] = field(default_factory=list)  # 부족한 정보 목록


def evaluate_layer(layer_schema: LayerSchema) -> QualityResult:
    """한 레이어의 추출 품질을 평가한다.

    Args:
        layer_schema: 레이어 에이전트가 추출한 결과

    Returns:
        QualityResult — 신뢰도와 부족 정보 포함
    """
    node_count = len(layer_schema.nodes)
    rel_count = len(layer_schema.relationships)
    missing: list[str] = []

    # 기본 신뢰도 계산 — 노드 수 기반
    if node_count == 0:
        confidence = 0.0
        missing.append(f"{layer_schema.layer} 레이어에서 노드가 추출되지 않았습니다")
    elif node_count == 1:
        confidence = 0.4
        missing.append(f"{layer_schema.layer} 레이어 노드가 1개뿐입니다 — 더 많은 정보가 필요합니다")
    elif node_count >= 10:
        confidence = 1.0
    else:
        # 2~9개: 0.5 ~ 0.9 선형 보간 (2→0.5, 9→0.9)
        confidence = 0.5 + (node_count - 2) * (0.4 / 7)

    # 관계 보너스 — 노드 간 관계가 있으면 더 의미 있는 결과
    if rel_count > 0 and confidence > 0.0:
        confidence = min(1.0, confidence + 0.05)

    # 이름 없는 노드 확인
    nameless = sum(1 for n in layer_schema.nodes if not n.get("name"))
    if nameless > 0:
        missing.append(f"{nameless}개 노드에 이름이 없습니다")

    # 설명 없는 노드 확인
    no_desc = sum(1 for n in layer_schema.nodes if not n.get("description"))
    if no_desc > 0 and node_count > 0:
        missing.append(f"{no_desc}개 노드에 설명이 없습니다")

    return QualityResult(
        confidence=round(confidence, 3),
        node_count=node_count,
        relation_count=rel_count,
        missing_info=missing,
    )
