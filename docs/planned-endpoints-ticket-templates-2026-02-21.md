# Planned 엔드포인트 구현 티켓 템플릿

기준 백로그: `docs/planned-endpoints-priority-backlog-2026-02-21.md`  
작성일: 2026-02-21

---

## 사용 규칙

- 티켓 상태: `TODO -> IN PROGRESS -> IN REVIEW -> DONE`
- 완료 공통 조건
  - 라우트 구현
  - 계약 테스트
  - 문서 상태(`Implemented/Partial/Planned`) 동기화
- 공통 증적 첨부
  - PR 링크
  - 테스트 로그
  - 변경 문서 링크

---

## P0 티켓 템플릿

## TKT-P0-CORE-WATCH-001

- 제목: Core Watch Alerts API 최소 구현
- 우선순위: P0
- 범위
  - `GET /api/v1/watches/alerts`
  - `PUT /api/v1/watches/alerts/{id}/acknowledge`
  - `PUT /api/v1/watches/alerts/read-all`
- 요구사항
  - tenant_id 격리
  - 기본 페이지네이션(`limit`, `cursor`)
  - 에러 응답 표준화
- 완료조건(DoD)
  - 위 3개 엔드포인트 200/4xx 동작 확인
  - `apps/canvas/src/lib/api/watch.ts` 경로 호출 성공
  - 문서 업데이트: `services/core/docs/02_api/watch-api.md`
- 테스트케이스
  - 정상 목록 조회
  - 타 테넌트 alert 접근 차단
  - acknowledge 후 상태 변경 검증
  - read-all 처리 건수 검증

## TKT-P0-CORE-WATCH-002

- 제목: Core Watch Subscriptions/Rules API 최소 구현
- 우선순위: P0
- 범위
  - `POST/GET/PUT/DELETE /api/v1/watches/subscriptions`
  - `POST/GET /api/v1/watches/rules`
- 요구사항
  - 룰 스키마 유효성 검증
  - 관리자 권한 체크(rules)
- 완료조건(DoD)
  - 구독 CRUD + 룰 생성/조회 동작
  - 문서 상태 `Planned -> Implemented` 전환
- 테스트케이스
  - 구독 생성/수정/삭제
  - 잘못된 rule payload 400
  - 비관리자 rules 생성 403

## TKT-P0-CORE-PROCESS-003

- 제목: Core Process Lifecycle 보강(`/submit` 외 핵심 경로)
- 우선순위: P0
- 범위
  - `POST /api/v1/process/initiate`
  - `GET /api/v1/process/{proc_inst_id}/status`
  - `GET /api/v1/process/{proc_inst_id}/workitems`
  - `POST /api/v1/process/approve-hitl`
  - `POST /api/v1/process/rework`
- 요구사항
  - 상태 전이 규칙 적용
  - 담당자/권한 검증
- 완료조건(DoD)
  - 프로세스 시작->HITL 승인/반려 흐름 동작
  - 상태 전이 회귀 테스트 통과
  - 문서 업데이트: `services/core/docs/02_api/process-api.md`
- 테스트케이스
  - initiate 성공/실패
  - approve-hitl approved=false feedback 필수
  - rework 후 상태 전이 확인

---

## P1 티켓 템플릿

## TKT-P1-SYN-ELOG-001

- 제목: Synapse Event Log API 1차 구현
- 우선순위: P1
- 범위
  - `/ingest`, `/`, `/{log_id}`, `/{log_id}/preview`, `/{log_id}/statistics`, `/{log_id}/column-mapping`, `/{log_id}/refresh`, `DELETE /{log_id}`
- 완료조건
  - 인제스트 task_id 발급
  - 목록/상세/미리보기 조회 가능
  - 컬럼 매핑 수정 가능
- 테스트케이스
  - CSV ingest -> status -> preview
  - 잘못된 매핑 422

## TKT-P1-SYN-EXT-002

- 제목: Synapse Extraction API 1차 구현
- 우선순위: P1
- 범위
  - extraction 시작/상태/결과
  - HITL confirm/review-queue
- 완료조건
  - 추출 비동기 상태머신(PENDING/RUNNING/COMPLETED/FAILED)
  - HITL 라우팅 분기 동작
- 테스트케이스
  - confidence 임계치별 분기
  - retry/revert 동작

## TKT-P1-ORA-META-003

- 제목: Oracle Meta API 1차 구현
- 우선순위: P1
- 범위
  - `/text2sql/meta/tables`
  - `/text2sql/meta/tables/{name}/columns`
  - `/text2sql/meta/datasources`
  - description 수정 2종
- 완료조건
  - 테이블/컬럼 메타 조회 가능
  - 관리자 설명 수정 가능
- 테스트케이스
  - 검색/페이지네이션
  - 비관리자 수정 403

## TKT-P1-CORE-GW-004

- 제목: Core Gateway EventLog/ProcessMining 프록시 구현
- 우선순위: P1
- 범위
  - `/api/v1/event-logs/*`
  - `/api/v1/process-mining/*`
- 완료조건
  - Core 경유 시 Synapse 라우팅 정상
  - 에러 코드 매핑 표준화
- 테스트케이스
  - 업스트림 정상/타임아웃/장애 시나리오

---

## P2 에픽 템플릿

## EPIC-P2-VISION-WHATIF

- 목표: Vision What-if 전 구간 구현
- 하위 티켓
  - CRUD
  - compute/status/result
  - compare/sensitivity/breakeven
  - process-simulation 연동
- 성공지표
  - 시나리오 end-to-end 통과율 100%

## EPIC-P2-VISION-OLAP

- 목표: 큐브/피벗/ETL API 구현
- 하위 티켓
  - cubes schema/upload/list/detail
  - pivot query/nl/drillthrough
  - etl analyze/sync/status

## EPIC-P2-WEAVER-CATALOG

- 목표: Weaver Metadata Catalog `/api/v1/metadata/*` 구현
- 하위 티켓
  - snapshots
  - glossary
  - tags
  - search/stats

## EPIC-P2-CORE-AGENT-MCP

- 목표: Core Agent/MCP API 구현
- 하위 티켓
  - agents chat/feedback/knowledge
  - completion endpoints
  - mcp config/tools/execute-tool

## EPIC-P2-ORACLE-EVENTS

- 목표: Oracle events API 구현 또는 Core Watch 완전 이관
- 하위 티켓
  - rules CRUD
  - scheduler start/stop/status
  - SSE alarms
  - watch-agent chat

