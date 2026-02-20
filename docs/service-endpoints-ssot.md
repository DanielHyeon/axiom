# Axiom Service Endpoints SSOT

> 기준일: 2026-02-19
> 상태: Accepted

## 목적

로컬 개발 환경에서 서비스별 호스트 포트, Canvas 환경 변수, 프록시 설정의 단일 기준(SSOT)을 정의한다.

## 정책

- 컨테이너 내부 포트는 서비스 문서 기본값을 유지한다 (`core/oracle/synapse/weaver=8000`, `vision=8400`).
- 로컬 호스트 바인딩 포트는 아래 표를 따른다.
- Canvas는 서비스 직접 호출 대신 환경 변수(`VITE_*_URL`)만 사용한다.

## 로컬 호스트 포트 매핑 (SSOT)

| 서비스 | 컨테이너 내부 포트 | 호스트 포트 | Base URL |
|------|----------------|---------|---------|
| Core | 8000 | 8000 | `http://localhost:8000/api/v1` |
| Weaver | 8000 | 8001 | `http://localhost:8001/api/v1` |
| Oracle | 8000 | 8002 | `http://localhost:8002/api/v1` |
| Synapse | 8000 | 8003 | `http://localhost:8003/api/v1` |
| Vision | 8400 | 8400 | `http://localhost:8400/api/v1` |
| Canvas | 3000 | 3000 | `http://localhost:3000` |

## Canvas 환경 변수 (SSOT)

```bash
VITE_CORE_URL=http://localhost:8000
VITE_WEAVER_URL=http://localhost:8001
VITE_ORACLE_URL=http://localhost:8002
VITE_SYNAPSE_URL=http://localhost:8003
VITE_VISION_URL=http://localhost:8400
VITE_WS_URL=ws://localhost:8000/ws
```

## 변경 규칙

- 포트 변경 시 본 문서를 먼저 수정하고, 이후 각 서비스 `08_operations/*` 및 Canvas 문서를 동기화한다.
- 서비스 경계 변경(직접 DB 접근/서비스 경유 등)은 ADR 반영 후에만 수정한다.
