"""보안 헤더 미들웨어 (Sprint 1 예정).

모든 응답에 표준 보안 헤더를 추가한다:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Strict-Transport-Security (HTTPS 환경)
등

Sprint 1에서 구현 예정. 현재는 스켈레톤만 제공한다.
"""
