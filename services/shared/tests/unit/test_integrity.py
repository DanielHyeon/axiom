"""이벤트 HMAC 무결성 서명/검증 테스트.

sign_event()와 verify_event()가 올바르게 작동하는지 검증한다.
변조 탐지, 키 순서 무관성, _hmac 필드 제외 등 엣지 케이스를 포함한다.
"""

from __future__ import annotations

import os
from unittest import mock

import pytest


# ─── 테스트용 이벤트 데이터 (fixture) ───

@pytest.fixture
def sample_event() -> dict:
    """테스트에 사용할 기본 이벤트 데이터."""
    return {
        "event_id": "abc123",
        "event_type": "SEMANTIC_ENTITY_PUBLISHED",
        "source_service": "synapse",
        "timestamp": "2026-03-24T09:00:00+00:00",
        "payload": {"entity_id": 42, "name": "매출액"},
    }


# ─── 1. 기본 서명/검증 ───

class TestSignAndVerify:
    """서명 생성 후 검증이 정상 통과하는 기본 시나리오."""

    def test_sign_returns_hex_string(self, sample_event: dict):
        """서명은 64자 hex 문자열이어야 한다 (SHA256 = 32바이트 = 64 hex)."""
        from shared.events.integrity import sign_event

        sig = sign_event(sample_event)
        assert isinstance(sig, str)
        assert len(sig) == 64
        # hex 문자열만 포함해야 한다
        assert all(c in "0123456789abcdef" for c in sig)

    def test_verify_passes_for_valid_signature(self, sample_event: dict):
        """올바른 서명은 검증을 통과해야 한다."""
        from shared.events.integrity import sign_event, verify_event

        sig = sign_event(sample_event)
        assert verify_event(sample_event, sig) is True

    def test_same_data_produces_same_signature(self, sample_event: dict):
        """동일한 데이터에 대해 항상 동일한 서명이 생성되어야 한다 (결정적)."""
        from shared.events.integrity import sign_event

        sig1 = sign_event(sample_event)
        sig2 = sign_event(sample_event)
        assert sig1 == sig2


# ─── 2. 변조 탐지 ───

class TestTamperDetection:
    """이벤트 데이터가 변조되면 서명 검증이 실패해야 한다."""

    def test_modified_payload_fails_verification(self, sample_event: dict):
        """payload를 변조하면 검증 실패."""
        from shared.events.integrity import sign_event, verify_event

        sig = sign_event(sample_event)
        # payload 변조
        sample_event["payload"]["entity_id"] = 999
        assert verify_event(sample_event, sig) is False

    def test_modified_event_type_fails_verification(self, sample_event: dict):
        """event_type을 변조하면 검증 실패."""
        from shared.events.integrity import sign_event, verify_event

        sig = sign_event(sample_event)
        sample_event["event_type"] = "QUALITY_THRESHOLD_BREACHED"
        assert verify_event(sample_event, sig) is False

    def test_added_field_fails_verification(self, sample_event: dict):
        """새 필드를 추가해도 서명이 깨져야 한다."""
        from shared.events.integrity import sign_event, verify_event

        sig = sign_event(sample_event)
        sample_event["injected_field"] = "malicious"
        assert verify_event(sample_event, sig) is False

    def test_removed_field_fails_verification(self, sample_event: dict):
        """필드를 삭제해도 서명이 깨져야 한다."""
        from shared.events.integrity import sign_event, verify_event

        sig = sign_event(sample_event)
        del sample_event["source_service"]
        assert verify_event(sample_event, sig) is False

    def test_wrong_signature_fails(self, sample_event: dict):
        """완전히 다른 서명 문자열로 검증하면 실패."""
        from shared.events.integrity import verify_event

        fake_sig = "a" * 64
        assert verify_event(sample_event, fake_sig) is False


# ─── 3. _hmac 필드 제외 ───

class TestHmacFieldExclusion:
    """서명 시 _hmac 필드가 자동으로 제외되어야 한다."""

    def test_hmac_field_excluded_from_signing(self, sample_event: dict):
        """_hmac 필드가 있어도 서명 결과가 동일해야 한다."""
        from shared.events.integrity import sign_event

        sig_without = sign_event(sample_event)
        sample_event["_hmac"] = "some-previous-signature"
        sig_with = sign_event(sample_event)
        assert sig_without == sig_with

    def test_verify_works_with_hmac_field_present(self, sample_event: dict):
        """_hmac 필드가 남아있는 상태에서도 검증이 올바르게 동작해야 한다."""
        from shared.events.integrity import sign_event, verify_event

        sig = sign_event(sample_event)
        sample_event["_hmac"] = sig
        # _hmac이 데이터에 있어도 검증 통과
        assert verify_event(sample_event, sig) is True


# ─── 4. 키 순서 무관성 ───

class TestKeyOrderIndependence:
    """딕셔너리 키 순서가 달라도 같은 데이터면 같은 서명이어야 한다."""

    def test_different_key_order_same_signature(self):
        """키 삽입 순서가 달라도 서명이 동일해야 한다."""
        from shared.events.integrity import sign_event

        event_a = {"event_type": "A", "source": "x", "value": 1}
        event_b = {"value": 1, "source": "x", "event_type": "A"}
        assert sign_event(event_a) == sign_event(event_b)


# ─── 5. 다른 서명 키 사용 시 ───

class TestSigningKeyIsolation:
    """서명 키가 다르면 서명도 달라야 한다."""

    def test_different_key_produces_different_signature(self, sample_event: dict):
        """환경변수로 다른 키를 설정하면 서명이 달라져야 한다."""
        from shared.events.integrity import sign_event

        sig_default = sign_event(sample_event)

        # 다른 키로 모듈을 다시 로드
        with mock.patch.dict(
            os.environ, {"EVENT_SIGNING_KEY": "totally-different-secret"}
        ):
            # 모듈 내부 _SIGNING_KEY를 직접 패치
            import shared.events.integrity as mod

            original_key = mod._SIGNING_KEY
            mod._SIGNING_KEY = b"totally-different-secret"
            try:
                sig_other = sign_event(sample_event)
                assert sig_default != sig_other
            finally:
                # 원래 키 복원
                mod._SIGNING_KEY = original_key


# ─── 6. 특수 데이터 타입 처리 ───

class TestSpecialDataTypes:
    """datetime 등 JSON 직렬화 불가 타입이 포함되어도 서명이 가능해야 한다."""

    def test_datetime_in_payload(self):
        """datetime 객체가 포함되어도 서명 생성이 성공해야 한다."""
        from datetime import datetime, timezone

        from shared.events.integrity import sign_event, verify_event

        event = {
            "event_type": "TEST",
            "created_at": datetime(2026, 3, 24, tzinfo=timezone.utc),
            "payload": {"ts": datetime.now(timezone.utc)},
        }
        sig = sign_event(event)
        assert isinstance(sig, str)
        assert len(sig) == 64
        # 같은 데이터면 같은 서명
        assert verify_event(event, sig) is True

    def test_empty_event(self):
        """빈 딕셔너리에도 서명을 생성할 수 있어야 한다."""
        from shared.events.integrity import sign_event, verify_event

        event: dict = {}
        sig = sign_event(event)
        assert isinstance(sig, str)
        assert verify_event(event, sig) is True

    def test_nested_dict_and_list(self):
        """중첩된 딕셔너리/리스트가 포함되어도 정상 동작해야 한다."""
        from shared.events.integrity import sign_event, verify_event

        event = {
            "event_type": "COMPLEX",
            "payload": {
                "tags": ["alpha", "beta"],
                "nested": {"a": {"b": {"c": 1}}},
            },
        }
        sig = sign_event(event)
        assert verify_event(event, sig) is True

        # 중첩 값 변조 시 실패
        event["payload"]["nested"]["a"]["b"]["c"] = 2
        assert verify_event(event, sig) is False
