"""이벤트 HMAC 무결성 서명/검증.

모든 Redis Streams 이벤트에 HMAC-SHA256 서명을 첨부하여
이벤트 변조/위조를 감지한다.

왜 필요한가?
    - Redis Streams를 통해 전달되는 이벤트가 중간에 변조되지 않았음을 보장해야 한다.
    - 서비스 간 신뢰 경계에서 메시지 무결성을 검증하는 것은 보안의 기본이다.
    - HMAC-SHA256은 비밀 키 없이는 서명을 위조할 수 없으므로 변조 탐지에 적합하다.

사용법:
    from shared.events.integrity import sign_event, verify_event

    # 발행자 측 — 이벤트에 서명 첨부
    event_data = {"event_type": "SEMANTIC_ENTITY_PUBLISHED", ...}
    signature = sign_event(event_data)
    event_data["_hmac"] = signature

    # 소비자 측 — 서명 검증 후 처리
    hmac_sig = event_data.pop("_hmac")
    is_valid = verify_event(event_data, hmac_sig)
    if not is_valid:
        logger.error("이벤트 무결성 검증 실패 — 변조 가능성 있음")
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os

logger = logging.getLogger("axiom.shared.events.integrity")

# 서명 키 — 환경변수에서 로드 (프로덕션에서는 반드시 설정해야 한다)
_SIGNING_KEY: bytes = os.getenv(
    "EVENT_SIGNING_KEY", "axiom-event-signing-key-dev"
).encode("utf-8")


def _canonical_payload(event_data: dict) -> bytes:
    """서명 대상 페이로드를 정규화한다.

    - _hmac 필드를 제외한다 (서명 자체는 서명 대상이 아니다)
    - JSON 직렬화 시 키를 알파벳 순으로 정렬해서 동일한 데이터면
      항상 동일한 바이트열이 나오도록 보장한다.
    - datetime 등 직렬화 불가 타입은 str()로 변환한다.
    """
    data = {k: v for k, v in event_data.items() if k != "_hmac"}
    return json.dumps(data, sort_keys=True, default=str).encode("utf-8")


def sign_event(event_data: dict) -> str:
    """이벤트 데이터에 HMAC-SHA256 서명을 생성한다.

    Args:
        event_data: 서명할 이벤트 딕셔너리 (_hmac 필드가 있으면 자동 제외)

    Returns:
        HMAC-SHA256 서명 문자열 (hex digest, 64자)
    """
    payload = _canonical_payload(event_data)
    signature = hmac.new(_SIGNING_KEY, payload, hashlib.sha256).hexdigest()
    logger.debug(
        "이벤트 서명 생성: event_type=%s, sig=%s...",
        event_data.get("event_type", "unknown"),
        signature[:12],
    )
    return signature


def verify_event(event_data: dict, signature: str) -> bool:
    """이벤트 서명을 검증한다.

    타이밍 공격을 방지하기 위해 hmac.compare_digest()를 사용한다.

    Args:
        event_data: 검증할 이벤트 딕셔너리 (_hmac 필드가 있으면 자동 제외)
        signature: 비교할 HMAC-SHA256 서명 문자열

    Returns:
        True면 서명 유효 (변조 없음), False면 서명 불일치 (변조 가능성)
    """
    expected = sign_event(event_data)
    is_valid = hmac.compare_digest(expected, signature)
    if not is_valid:
        logger.warning(
            "이벤트 무결성 검증 실패: event_type=%s — 변조 가능성 있음",
            event_data.get("event_type", "unknown"),
        )
    return is_valid
