"""Redis 기반 토큰 블랙리스트.

로그아웃·계정 정지·비밀번호 변경 시
아직 만료되지 않은 JWT를 즉시 무효화하기 위해 사용한다.

두 가지 무효화 방식을 지원한다:
1. JTI(JWT ID) 단위 — 특정 토큰 1개만 무효화 (로그아웃)
2. 사용자 단위 — 해당 사용자의 모든 토큰 무효화 (계정 정지, 비밀번호 변경)

Redis 장애 시에는 검사를 건너뛰어 인증 전체가 막히지 않도록 한다 (fail-open).
이 동작은 Feature Flag `FF_TOKEN_BLACKLIST`로 전체 기능을 끌 수 있다.

Redis 키 설계:
- JTI 블랙리스트:   `bl:jti:{jti}`          → 값 "1", TTL = 토큰 잔여 수명
- 사용자 전체 무효화: `bl:user:{user_id}`    → 값 = Unix 타임스탬프, TTL = max_token_ttl

사용법:
    from shared.auth.token_blacklist import TokenBlacklist

    blacklist = TokenBlacklist(redis_client)

    # 로그아웃 — 이 토큰 하나만 무효화
    await blacklist.revoke_token(jti="abc123", ttl_seconds=300)

    # 계정 정지 — 사용자의 모든 토큰 무효화
    await blacklist.revoke_all_user_tokens(user_id="user-42")

    # 토큰 검증 시 — 블랙리스트에 있는지 확인
    if await blacklist.is_revoked(jti="abc123", user_id="user-42", issued_at=1711234000.0):
        raise Unauthorized("Token revoked")
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger("axiom.auth.blacklist")

# Redis 키 접두사 — 다른 키와 충돌하지 않도록 네임스페이스를 분리한다
_JTI_PREFIX = "bl:jti:"
_USER_PREFIX = "bl:user:"


class TokenBlacklist:
    """Redis 기반 토큰 블랙리스트.

    Args:
        redis_client: aioredis(redis-py async) 클라이언트 인스턴스.
            None이면 모든 메서드가 no-op(통과)으로 동작한다.
    """

    def __init__(self, redis_client=None) -> None:
        self.redis = redis_client

    # ── 1) 단일 토큰 무효화 (로그아웃) ──────────────────────────

    async def revoke_token(self, jti: str, ttl_seconds: int) -> None:
        """특정 토큰 1개를 무효화한다.

        JTI(JWT ID)를 Redis에 기록하여 해당 토큰이 이후 사용되지 못하게 한다.
        TTL은 토큰의 남은 수명과 같게 설정해야 한다 — 토큰이 자연 만료되면
        Redis 키도 자동 삭제되므로 공간이 무한히 늘어나지 않는다.

        Args:
            jti: JWT의 고유 식별자 (JWT ID 클레임)
            ttl_seconds: Redis 키 유지 시간 (초). 토큰의 잔여 만료 시간.
        """
        if self.redis is None:
            return
        try:
            key = f"{_JTI_PREFIX}{jti}"
            # SET + EX: 값 "1"을 넣고 TTL 설정 (원자적)
            await self.redis.set(key, "1", ex=max(1, ttl_seconds))
            logger.info("토큰 무효화 완료: jti=%s, ttl=%ds", jti, ttl_seconds)
        except Exception:
            # Redis 장애 시 로그만 남기고 넘어간다 (fail-open)
            logger.warning("토큰 무효화 실패 (fail-open): jti=%s", jti, exc_info=True)

    # ── 2) 사용자 전체 토큰 무효화 (계정 정지, 비밀번호 변경) ──

    async def revoke_all_user_tokens(
        self, user_id: str, max_token_ttl: int = 900
    ) -> None:
        """해당 사용자의 모든 토큰을 무효화한다.

        현재 시각을 Redis에 기록하여, 이 시각 이전에 발급된 모든 토큰이
        is_revoked() 검사에서 거부되도록 한다.

        Args:
            user_id: 무효화할 사용자의 ID
            max_token_ttl: Redis 키 유지 시간 (초).
                Access Token의 최대 수명(기본 15분=900초)과 같게 설정한다.
                이 시간이 지나면 모든 구 토큰이 자연 만료되므로 키를 삭제해도 안전하다.
        """
        if self.redis is None:
            return
        try:
            key = f"{_USER_PREFIX}{user_id}"
            # 현재 시각을 문자열로 저장한다 — is_revoked()에서 issued_at과 비교
            revoked_at = str(time.time())
            await self.redis.set(key, revoked_at, ex=max(1, max_token_ttl))
            logger.info(
                "사용자 전체 토큰 무효화 완료: user_id=%s, ttl=%ds",
                user_id,
                max_token_ttl,
            )
        except Exception:
            logger.warning(
                "사용자 전체 토큰 무효화 실패 (fail-open): user_id=%s",
                user_id,
                exc_info=True,
            )

    # ── 3) 토큰 무효화 여부 확인 ──────────────────────────────

    async def is_revoked(
        self, jti: str, user_id: str, issued_at: float
    ) -> bool:
        """토큰이 무효화되었는지 확인한다.

        두 가지를 순서대로 확인한다:
        1. JTI가 블랙리스트에 있는가? → 있으면 True (개별 무효화됨)
        2. 사용자 전체 무효화 시각이 토큰 발급 시각 이후인가?
           → 그렇다면 True (사용자 전체 무효화 이후 발급된 토큰이 아님)

        Redis 장애 시에는 False를 반환한다 (fail-open).
        블랙리스트 검사가 실패해도 사용자가 서비스를 이용할 수 있도록 하기 위함이다.

        Args:
            jti: JWT의 고유 식별자
            user_id: 토큰 소유자의 사용자 ID
            issued_at: 토큰이 발급된 Unix 타임스탬프 (iat 클레임)

        Returns:
            True이면 토큰이 무효화된 상태 (거부해야 함)
        """
        if self.redis is None:
            return False
        try:
            # ── 확인 1: JTI 개별 블랙리스트 ──
            jti_key = f"{_JTI_PREFIX}{jti}"
            if await self.redis.exists(jti_key):
                return True

            # ── 확인 2: 사용자 전체 무효화 ──
            user_key = f"{_USER_PREFIX}{user_id}"
            revoked_at_raw = await self.redis.get(user_key)
            if revoked_at_raw is not None:
                # Redis에서 문자열로 저장했으므로 float으로 변환
                revoked_at = float(
                    revoked_at_raw
                    if isinstance(revoked_at_raw, str)
                    else revoked_at_raw.decode()
                )
                # 토큰이 무효화 시각 *이전에* 발급되었으면 거부
                if issued_at < revoked_at:
                    return True

            return False

        except Exception:
            # Redis 장애 시 통과시킨다 (fail-open)
            logger.warning(
                "블랙리스트 확인 실패 (fail-open): jti=%s, user_id=%s",
                jti,
                user_id,
                exc_info=True,
            )
            return False
