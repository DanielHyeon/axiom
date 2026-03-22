"""Fernet 기반 비밀번호 암호화 유틸리티.

데이터소스 비밀번호를 안전하게 저장하기 위해 Fernet 대칭키 암호화를 사용한다.
- 암호화된 값은 "enc:<base64 암호문>" 형식으로 저장
- "enc:" 접두어가 없는 값은 레거시 평문으로 간주하여 그대로 반환
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("axiom.weaver.crypto")

# ── 암호화 키 로딩 ── #
# 1순위: 환경변수 WEAVER_ENCRYPTION_KEY
# 2순위: .encryption_key 파일 (개발 전용 — 자동 생성)

_ENC_PREFIX = "enc:"


def _load_or_generate_key() -> bytes:
    """암호화 키를 환경변수 또는 파일에서 불러온다.

    환경변수가 없으면 프로젝트 루트의 .encryption_key 파일을 사용하며,
    해당 파일이 없으면 새 키를 생성해 저장한다 (개발 환경 전용).
    """
    env_key = os.getenv("WEAVER_ENCRYPTION_KEY", "")
    if env_key:
        logger.debug("암호화 키를 환경변수에서 로드")
        return env_key.encode()

    # 개발 모드: .encryption_key 파일에서 로드 또는 자동 생성
    key_path = Path(__file__).resolve().parent.parent.parent / ".encryption_key"
    if key_path.exists():
        logger.debug("암호화 키를 파일에서 로드: %s", key_path)
        return key_path.read_text(encoding="utf-8").strip().encode()

    # 신규 키 생성 (개발 환경에서만 사용)
    new_key = Fernet.generate_key()
    key_path.write_bytes(new_key)
    logger.warning(
        "암호화 키 자동 생성 (개발 전용): %s — 프로덕션에서는 WEAVER_ENCRYPTION_KEY 환경변수를 설정하세요",
        key_path,
    )
    return new_key


def _get_fernet() -> Fernet:
    """Fernet 인스턴스를 반환한다 (모듈 수준 싱글톤)."""
    return Fernet(_load_or_generate_key())


def encrypt_password(plain: str) -> str:
    """평문 비밀번호를 Fernet으로 암호화하여 'enc:<base64>' 형식으로 반환한다.

    Args:
        plain: 암호화할 평문 비밀번호

    Returns:
        'enc:<base64 암호문>' 형식의 암호화된 문자열
    """
    if not plain:
        return plain
    f = _get_fernet()
    token = f.encrypt(plain.encode("utf-8"))
    return f"{_ENC_PREFIX}{base64.urlsafe_b64encode(token).decode('ascii')}"


def decrypt_password(stored: str) -> str:
    """저장된 비밀번호를 복호화한다.

    'enc:' 접두어가 있으면 Fernet 복호화를 수행하고,
    없으면 레거시 평문으로 간주하여 그대로 반환한다.

    Args:
        stored: 저장된 비밀번호 문자열

    Returns:
        복호화된 평문 비밀번호
    """
    if not stored:
        return stored
    if not stored.startswith(_ENC_PREFIX):
        # 레거시 평문 — 그대로 반환
        return stored

    cipher_b64 = stored[len(_ENC_PREFIX):]
    try:
        token = base64.urlsafe_b64decode(cipher_b64.encode("ascii"))
        f = _get_fernet()
        return f.decrypt(token).decode("utf-8")
    except (InvalidToken, Exception) as exc:
        logger.error("비밀번호 복호화 실패: %s", exc)
        raise ValueError("비밀번호 복호화에 실패했습니다") from exc
