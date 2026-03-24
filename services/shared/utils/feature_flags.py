"""환경변수 기반 Feature Flag / Kill Switch.

고위험 기능의 안전한 롤아웃을 위해 환경변수로 기능을 켜고 끌 수 있다.
Redis 등 외부 의존 없이 환경변수만으로 동작하여 장애 상황에서도 안정적이다.

환경변수 규칙:
- 접두사: FF_  (Feature Flag의 약자)
- 예: FF_TOKEN_BLACKLIST=true → TOKEN_BLACKLIST 플래그 활성화
- 대소문자 구분 없음 — "true", "True", "TRUE", "1", "yes", "on" 모두 활성화

사용법:
    from shared.utils.feature_flags import is_enabled, get_all_flags

    # 단일 플래그 확인
    if is_enabled("TOKEN_BLACKLIST"):
        await check_blacklist(token)

    # 모든 플래그 상태 조회 (디버깅, 헬스체크 등)
    flags = get_all_flags()
    # → {"CSP_ENFORCE": False, "TOKEN_BLACKLIST": True, ...}
"""
from __future__ import annotations

import os

# ── 기본 플래그 값 ──
# 환경변수(FF_XXX)가 설정되지 않았을 때 이 값을 사용한다.
# 새 기능을 추가할 때 여기에 등록하면 된다.
_DEFAULTS: dict[str, bool] = {
    # --- 보안 ---
    "CSP_ENFORCE": False,           # CSP Report-Only → enforcing 전환
    "TOKEN_BLACKLIST": False,       # 토큰 블랙리스트 검사 활성화

    # --- 안정성 ---
    "CIRCUIT_BREAKER": False,       # Circuit Breaker 패턴 활성화
    "FAIL_SILENT_EVENTS": True,     # 이벤트 발행 실패 시 무시 (True = 안전 모드)

    # --- 기능 공개 ---
    "SNAPSHOT_COMPARE_API": False,  # 스냅샷 비교 API 공개 여부
    "LAZY_WITH_RETRY": True,        # lazyWithRetry 활성화

    # --- 품질 ---
    "QUALITY_AUTO_SCAN": False,     # 시멘틱 엔티티 발행 시 자동 품질 스캔
}

# 활성화로 인식하는 문자열 목록 (소문자 비교)
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def is_enabled(flag_name: str) -> bool:
    """Feature Flag가 활성화되었는지 확인한다.

    확인 순서:
    1. 환경변수 FF_{flag_name} 이 있으면 그 값을 사용한다.
    2. 없으면 _DEFAULTS에서 기본값을 찾는다.
    3. _DEFAULTS에도 없으면 False (비활성화)를 반환한다.

    Args:
        flag_name: 플래그 이름 (예: "TOKEN_BLACKLIST"). FF_ 접두사는 붙이지 않는다.

    Returns:
        True이면 기능이 활성화된 상태
    """
    env_key = f"FF_{flag_name}"
    env_val = os.getenv(env_key)
    if env_val is not None:
        return env_val.strip().lower() in _TRUTHY
    return _DEFAULTS.get(flag_name, False)


def get_all_flags() -> dict[str, bool]:
    """등록된 모든 Feature Flag의 현재 상태를 반환한다.

    _DEFAULTS에 정의된 모든 플래그를 순회하면서
    환경변수 오버라이드가 있으면 적용한 결과를 돌려준다.

    Returns:
        플래그 이름 → 현재 활성화 여부 딕셔너리
    """
    return {name: is_enabled(name) for name in sorted(_DEFAULTS)}


def register_flag(flag_name: str, default: bool = False) -> None:
    """런타임에 새 플래그를 등록한다.

    서비스 시작 시 서비스 고유 플래그를 추가할 때 사용한다.
    이미 등록된 플래그가 있으면 기본값을 덮어쓰지 않는다.

    Args:
        flag_name: 플래그 이름 (FF_ 접두사 없이)
        default: 환경변수가 없을 때 사용할 기본값
    """
    if flag_name not in _DEFAULTS:
        _DEFAULTS[flag_name] = default
