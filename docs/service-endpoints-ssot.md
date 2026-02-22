# Axiom Service Endpoints SSOT

> 기준일: 2026-02-22
> 상태: Synced (현재 배포 파일 기준)
> 기준 파일: `docker-compose.yml`, `k8s/deployments.yaml`, `k8s/services.yaml`, `k8s/configmaps.yaml`

## 목적

로컬/클러스터 환경에서 실제 배포 중인 서비스의 포트와 Canvas 환경 변수 기준을 단일 문서로 관리한다.

## 1. 현재 배포 프로파일 (Runtime-Active)

현재 저장소의 Compose/K8s 매니페스트 기준으로 활성화된 서비스는 아래 6개다.

| 서비스 | 컨테이너 포트 | 호스트 포트(로컬) | Base URL |
|---|---:|---:|---|
| Postgres DB | 5432 | 5432 | `postgresql://localhost:5432/insolvency_os` |
| Core | 8002 | 8002 | `http://localhost:8002` |
| Vision | 8000 | 8000 | `http://localhost:8000` |
| Weaver | 8001 | 8001 | `http://localhost:8001` |
| Canvas | 80 | 5173 | `http://localhost:5173` |
| Redis Bus | 6379 | 6379 | `redis://localhost:6379` |

## 2. Canvas 환경 변수 (현재 프로파일)

```bash
# .env.development (현재 Compose 프로파일)
VITE_VISION_URL=http://localhost:8000
VITE_WEAVER_URL=http://localhost:8001
VITE_WS_URL=ws://localhost:8000/ws
```

참고:
- `VITE_ORACLE_URL`, `VITE_SYNAPSE_URL`는 현재 Compose/K8s 프로파일에서 기본 제공되지 않는다.
- 필요한 경우 별도 실행(로컬 개별 기동/추가 매니페스트) 후 환경 변수를 개별 주입한다.

## 3. 확장 목표 프로파일 (Runtime-Target)

아래는 전 서비스 통합 운영 시 목표 포트 맵이다. 현재 매니페스트에는 완전 반영되지 않았다.

| 서비스 | 목표 호스트 포트 | 목표 Base URL |
|---|---:|---|
| Core | 8002 | `http://localhost:8002/api/v1` |
| Weaver | 8001 | `http://localhost:8001/api/v1` |
| Oracle | 8002 | `http://localhost:8002/api/v1` |
| Synapse | 8003 | `http://localhost:8003/api/v1` |
| Vision | 8400 | `http://localhost:8400/api/v1` |
| Canvas | 3000 | `http://localhost:3000` |

## 4. 변경 규칙

1. 포트/서비스 변경 시 `docker-compose.yml` 또는 `k8s/*.yaml`을 먼저 수정한다.
2. 이후 본 문서를 같은 커밋에서 동기화한다.
3. Canvas 문서(`apps/canvas/docs/01_architecture/api-integration.md`, `apps/canvas/docs/08_operations/build-deploy.md`)의 로컬 예시도 함께 갱신한다.
4. full-spec 진행 항목은 `docs/full-spec-gap-analysis-2026-02-22.md`를 기준으로 추적한다.
5. 변경 후 `python3 tools/validate_ssot.py`로 Runtime-Active 정합성을 검증한다.
