# 테스트 계정 및 로컬 접속

## 프론트엔드 접속

- **URL**: http://localhost:5173 (Docker Compose 기동 시)
- Canvas UI가 5173 포트로 노출됨.

## 테스트 계정

Canvas는 Core API(`/api/v1/auth/login`) 로그인 실패 시 **모의 로그인(mock fallback)**으로 동작한다.  
이때 **아무 이메일/비밀번호**로도 로그인되며, 입력한 이메일과 **admin** 역할로 세션이 생성된다.

E2E/문서에서 통일해 쓰는 테스트 계정은 아래와 같다.

| 용도 | 이메일 | 비밀번호 |
|------|--------|----------|
| 관리자(admin) | `admin@axiom.ai` | `password` |
| 변호사(attorney) | `test-attorney@axiom.ai` | `password` |

- **실제 Core 인증**을 쓰는 환경에서는 위 계정이 DB에 시드되어 있어야 하며, 현재는 시드 스크립트 여부를 확인해야 함.
- **Compose/로컬 개발**에서는 Core 로그인 실패 시 모의 로그인이 동작하므로 위 계정으로 입력하면 admin 권한으로 진입 가능.

## 백엔드 헬스 (참고)

| 서비스 | 포트 | 헬스 예시 |
|--------|------|-----------|
| Vision | 8000 | http://localhost:8000/health/ready |
| Weaver | 8001 | http://localhost:8001/health/ready |
| Core | 8002 | http://localhost:8002/api/v1/health/ready |
| Synapse | 8003 | http://localhost:8003/health/live |
| Oracle | 8004 | http://localhost:8004/health/ready |
