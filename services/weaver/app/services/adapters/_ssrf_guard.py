"""공유 SSRF 방어 유틸리티.

S3 어댑터에 있던 _validate_endpoint_url()을 공통 모듈로 추출.
REST API, GraphQL 등 사용자 제공 URL을 받는 모든 어댑터에서 사용한다.

차단 대상:
- AWS 메타데이터 (169.254.0.0/16)
- RFC 1918 내부 네트워크 (10/8, 172.16/12, 192.168/16)
- 루프백 (127/8, ::1)
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# 차단 네트워크 목록
_BLOCKED_NETS = [
    ipaddress.ip_network("169.254.0.0/16"),  # AWS 메타데이터
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
]

_ALLOWED_SCHEMES = {"http", "https"}

# 인증 헤더 허용 목록 (C4 반영)
_ALLOWED_AUTH_HEADERS = {
    "authorization", "x-api-key", "x-auth-token",
    "api-key", "bearer", "token", "x-api-secret",
}


def validate_external_url(url: str, label: str = "URL") -> str:
    """사용자 제공 URL의 SSRF 검증 — 내부 네트워크 차단.

    Args:
        url: 검증할 URL
        label: 에러 메시지에 사용할 필드명

    Returns:
        검증 통과한 URL (원본)

    Raises:
        ValueError: SSRF 위험이 감지된 경우
    """
    if not url:
        raise ValueError(f"{label}이 비어있습니다")

    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"허용되지 않는 프로토콜: {parsed.scheme} ({label})")

    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError(f"호스트명이 비어있습니다 ({label})")

    try:
        resolved = socket.getaddrinfo(hostname, parsed.port or 443)
        for _, _, _, _, addr in resolved:
            ip = ipaddress.ip_address(addr[0])
            for net in _BLOCKED_NETS:
                if ip in net:
                    raise ValueError(
                        f"내부 네트워크 접근 차단: {hostname} → {ip} ({label})"
                    )
    except socket.gaierror:
        pass  # DNS 해석 실패는 연결 시점에서 처리

    return url


def validate_auth_header(name: str) -> str:
    """인증 헤더명 허용 목록 검증 + CRLF 인젝션 차단 (C4 반영)."""
    if "\r" in name or "\n" in name:
        raise ValueError("헤더명에 금지 문자 포함")
    if name.lower().strip() not in _ALLOWED_AUTH_HEADERS:
        raise ValueError(f"허용되지 않는 인증 헤더: {name}")
    return name


def validate_header_value(value: str) -> str:
    """헤더 값 CRLF 인젝션 차단."""
    if "\r" in value or "\n" in value:
        raise ValueError("헤더 값에 금지 문자 포함")
    return value
