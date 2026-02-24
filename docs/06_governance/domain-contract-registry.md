# Domain Event Contract Registry

## 1. 목적
- Core/Synapse/Vision/Weaver 간 이벤트 계약을 단일 규격으로 관리한다.
- 이벤트 스키마 변경 시 브레이킹 변경을 사전에 식별하고 승인 절차를 강제한다.

## 2. 필수 메타필드
- `event_name`: 도메인 이벤트 명
- `owner_service`: 계약 소유 서비스
- `version`: SemVer (`major.minor.patch`)
- `payload_schema`: JSON Schema 식별자 또는 경로
- `idempotency_key_rule`: 중복 제거 키 생성 규칙
- `retention`: 보존 기간
- `consumer_groups`: 소비자/그룹 목록

## 2.1 주요 서비스별 이벤트 타입 매핑표

| 서비스 (Owner) | 대표 이벤트 명 (`event_name`) | 주요 용도 | 비고 |
|---|---|---|---|
| **Core** | `core.resource.created`, `core.access.granted` | 공통 리소스 및 인가 감지 | 전사 기본 리소스 라이프사이클 통제 |
| **Synapse** | `synapse.ontology.updated`, `synapse.entity.extracted` | 온톨로지 변동, 비정형/레거시 모델 추출 | 시맨틱 레이어/지식 그래프 변동 알림 |
| **Vision** | `vision.whatif.computed`, `vision.rootcause.detected` | 시뮬레이션 및 분석/진단 산출물 생성 | 이상 감지 및 예측 분석 결과 전파 |
| **Weaver** | `weaver.metadata.synced`, `weaver.snapshot.taken` | Data Fabric 메타데이터 동기화 | 원천 DB 스키마/상태 변경 알림 |

## 3. 버전 정책
1. `major`
- payload 필수 필드 제거/타입 변경/의미 변경 시 증가
2. `minor`
- 하위 호환 필드 추가 시 증가
3. `patch`
- 설명/예시/옵션 기본값 수정 등 비기능 변경

## 4. 승인 및 검증 규칙 (Breaking-Change Flow)
- `major` 변경 시 기존 Consumer와의 호환성 충돌 체크(Zero-Collision Verification)를 파이프라인에서 자동 검증한다. 서비스 간 이벤트 계약 충돌(이름/버전 불일치)이 0건일 때만 PR을 승인한다.
- `major` 변경은 프로그램 레벨 승인(`code-reviewer`, `api-developer`, `backend-developer`)이 필요하다.
- 승인 전에는 Producer/Consumer 배포를 동시 진행하지 않는다.

## 4.1 핵심 이벤트 통과 기준 (Pass Criteria)
- 핵심 도메인 이벤트의 100%는 반드시 `owner_service`, `version`, `payload_schema`, `idempotency_key_rule`의 메타필드를 포함해야 한다. 누락된 이벤트는 병합이 거부된다.

## 5. DB 연계 규칙
- `event_outbox.event_type`는 Registry에 등록된 이름만 허용한다.
- `watch_alerts.event_type`도 동일 Registry를 참조한다.
- 이벤트 계약은 `docs/03_implementation/program/09_agent-governance-and-acceptance.md`의 Sprint Exit 증적으로 첨부한다.
