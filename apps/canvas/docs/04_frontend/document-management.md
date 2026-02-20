# 문서 관리 + HITL 리뷰 UI

<!-- affects: frontend, api -->
<!-- requires-update: 02_api/api-contracts.md (Core API) -->

## 이 문서가 답하는 질문

- 문서 관리 UI의 화면 구성은 어떻게 되는가?
- HITL(Human-in-the-Loop) 리뷰 워크플로우는 어떻게 동작하는가?
- AI 생성 문서와 인간 수정본의 Diff는 어떻게 표시하는가?
- 인라인 코멘트와 승인 프로세스는?

---

## 1. HITL 리뷰 워크플로우

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  AI 초안  │────→│ 리뷰 배정 │────→│ 인라인   │────→│ 수정 반영 │────→│ 최종 승인│
│  생성     │     │          │     │ 코멘트   │     │          │     │          │
│          │     │ 검토자   │     │ 추가     │     │ 저자가   │     │ 승인자가 │
│ Core API │     │ 1명 이상 │     │          │     │ 수정     │     │ 승인     │
└──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
   draft          in_review        in_review       in_review          approved
                                                   changes_requested
```

### 1.1 문서 상태 전이

```
draft ──→ in_review ──→ approved
                    ──→ changes_requested ──→ in_review (재검토)
                    ──→ rejected
approved ──→ archived
```

---

## 2. 문서 목록 화면

```
┌──────────────────────────────────────────────────────────────────────┐
│ 📁 케이스: 물류최적화 프로젝트 (2024-PRJ-100123) > 문서               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  [+ 새 문서] [AI 생성 요청]                     🔍 문서 검색         │
│                                                                      │
│  필터: [전체 유형 ▼] [전체 상태 ▼] [AI 생성 ▼]                      │
│                                                                      │
│  ┌─────┬────────────────┬──────────┬────────┬──────┬───────────┐   │
│  │     │ 문서명          │ 유형      │ 상태    │ 버전  │ 최종 수정  │   │
│  ├─────┼────────────────┼──────────┼────────┼──────┼───────────┤   │
│  │ 🤖 │ 이해관계자목록v3│ 참여자목록│ ● 검토중│ v3   │ 2시간 전   │   │
│  │ 📝 │ 실행 계획서     │ 실행계획  │ ◐ 수정요│ v5   │ 1일 전     │   │
│  │ 🤖 │ 자산 보고서     │ 자산보고  │ ✓ 승인됨│ v2   │ 3일 전     │   │
│  │ 📝 │ 1차 회의록      │ 회의록   │ ○ 초안  │ v1   │ 방금       │   │
│  └─────┴────────────────┴──────────┴────────┴──────┴───────────┘   │
│                                                                      │
│  🤖 = AI 생성  📝 = 수동 작성                                       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. 문서 편집 + 리뷰 화면

```
┌──────────────────────────────────────────────────────────────────────┐
│ 📄 이해관계자 목록 v3                [Diff 보기] [히스토리] [승인]   │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────┐ ┌────────────────────────┐│
│  │  문서 편집기 (Monaco Editor)          │ │ 리뷰 패널              ││
│  │                                       │ │                        ││
│  │  1  # 이해관계자 목록                 │ │ 리뷰 상태: 검토 중     ││
│  │  2                                    │ │ 검토자: 박전문가       ││
│  │  3  ## 1. 핵심 이해관계자             │ │ 기한: 2024-03-15       ││
│  │  4                                    │ │                        ││
│  │  5  | 참여자 | 예산 | 순위 |          │ │ ─── 코멘트 (3) ───    ││
│  │  6  |--------|------|------|          │ │                        ││
│  │  7  | 운영팀 | 12억 | 1순위|  💬 ←───┤─┤ 💬 줄 7-8             ││
│  │  8  | 전략팀 | 5억  | 1순위|          │ │ "운영팀 예산 확인      ││
│  │  9                                    │ │  필요합니다. 12억이    ││
│  │ 10  ## 2. 일반 이해관계자             │ │  맞는지?"              ││
│  │ 11                                    │ │ - 박전문가 (2시간 전)  ││
│  │ 12  | 참여자 | 예산 | 비율 |          │ │                        ││
│  │ 13  |--------|------|------|          │ │ [답변 작성...]         ││
│  │ 14  | 마케팅 | 50억 | 35%  |  💬 ←───┤─┤                        ││
│  │ 15  | 개발팀 | 30억 | 21%  |          │ │ 💬 줄 14              ││
│  │ 16  | 디자인 | 20억 | 14%  |          │ │ "마케팅 비율 재계산    ││
│  │ ...                                   │ │  해주세요"             ││
│  │                                       │ │ - 박전문가 (1시간 전)  ││
│  │                                       │ │ ✓ 해결됨               ││
│  │                                       │ │                        ││
│  │                                       │ │ 💬 줄 전체             ││
│  │                                       │ │ "전반적으로 양호하나   ││
│  │                                       │ │  금액 검증 필요"       ││
│  │                                       │ │ - 박전문가 (30분 전)   ││
│  │                                       │ │                        ││
│  │  [저장] [되돌리기]                    │ │ [코멘트 추가]          ││
│  └──────────────────────────────────────┘ └────────────────────────┘│
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. Diff 뷰어 화면

```
┌──────────────────────────────────────────────────────────────────────┐
│ 📄 이해관계자 목록 - Diff 보기    [AI 원본 vs 현재] [v2 vs v3]      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────┐ ┌─────────────────────────────┐   │
│  │  AI 원본 (v1)                │ │  현재 (v3)                   │   │
│  │                              │ │                              │   │
│  │  # 이해관계자 목록           │ │  # 이해관계자 목록           │   │
│  │                              │ │                              │   │
│  │  ## 1. 핵심 이해관계자      │ │  ## 1. 핵심 이해관계자      │   │
│  │                              │ │                              │   │
│  │  | 참여자 | 예산 | 순위 |    │ │  | 참여자 | 예산 | 순위 |    │   │
│  │- | 운영팀 | 10억 | 1순위|    │ │+ | 운영팀 | 12억 | 1순위|    │   │
│  │  | 서울시 | 5억  | 1순위|    │ │  | 서울시 | 5억  | 1순위|    │   │
│  │                              │ │                              │   │
│  │  ## 2. 일반 이해관계자       │ │  ## 2. 일반 이해관계자       │   │
│  │                              │ │                              │   │
│  │- | 마케팅 | 50억 | 33%  |    │ │+ | 마케팅 | 50억 | 35%  |    │   │
│  │  | 개발팀 | 30억 | 20%  |    │ │+ | 개발팀 | 30억 | 21%  |    │   │
│  │                              │ │+ | 디자인 | 20억 | 14%  |    │   │
│  │                              │ │                              │   │
│  │  변경: 2줄 수정              │ │  변경: 2줄 수정, 1줄 추가    │   │
│  └─────────────────────────────┘ └─────────────────────────────┘   │
│                                                                      │
│  통계: AI 원본 대비 수정률 15% │ 승인까지 평균 2.3일               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 5. 컴포넌트 분해

```
DocumentListPage
├── DocumentList
│   ├── shared/DataTable
│   ├── StatusBadge
│   └── AiGeneratedBadge (🤖 표시)

DocumentEditorPage
├── DocumentEditor
│   └── Monaco Editor (react-monaco-editor)
├── ReviewPanel
│   ├── ReviewStatus
│   ├── InlineComment (x N)
│   │   ├── CommentThread
│   │   └── CommentReply
│   └── AddCommentForm
├── DocumentDiffViewer
│   └── react-diff-viewer-continued
└── ApprovalWorkflow
    ├── ApprovalButton
    ├── RejectButton
    └── RequestChangesButton
```

---

## 6. API 연동

### 6.1 문서 CRUD + 리뷰 엔드포인트

문서 관리 UI는 Core API의 문서 관련 엔드포인트를 사용한다. 모든 경로는 케이스 스코프이다.

| 기능 | Method | Path | 설명 |
|------|--------|------|------|
| 문서 목록 | GET | `/api/v1/cases/{caseId}/documents` | 케이스 내 문서 목록 |
| 문서 상세 | GET | `/api/v1/cases/{caseId}/documents/{docId}` | 문서 내용 + 메타데이터 |
| 문서 생성 | POST | `/api/v1/cases/{caseId}/documents` | 새 문서 (draft) |
| 문서 수정 | PUT | `/api/v1/cases/{caseId}/documents/{docId}` | 내용 업데이트 |
| 리뷰 요청 | POST | `/api/v1/cases/{caseId}/documents/{docId}/review` | draft → in_review |
| 코멘트 목록 | GET | `/api/v1/cases/{caseId}/documents/{docId}/comments` | 인라인 코멘트 |
| 코멘트 추가 | POST | `/api/v1/cases/{caseId}/documents/{docId}/comments` | 줄 범위 코멘트 |
| 승인 | POST | `/api/v1/cases/{caseId}/documents/{docId}/approve` | in_review → approved |
| 반려 | POST | `/api/v1/cases/{caseId}/documents/{docId}/reject` | in_review → rejected |
| 수정 요청 | POST | `/api/v1/cases/{caseId}/documents/{docId}/request-changes` | → changes_requested |
| 버전 목록 | GET | `/api/v1/cases/{caseId}/documents/{docId}/versions` | 자동 버저닝 |
| 버전 비교 | GET | `/api/v1/cases/{caseId}/documents/{docId}/diff?from=v1&to=v2` | Diff 데이터 |

> **백엔드 협의 필요**: 위 엔드포인트 목록은 프론트엔드 요구사항 기반 설계이다. Core API 문서 관리 모듈의 실제 API 스펙이 확정되면 경로/필드를 동기화해야 한다.

### 6.2 온톨로지 추출 HITL (Synapse API)

문서에서 추출된 온톨로지(개체/관계)의 HITL 검토는 Synapse API를 사용한다.

| 기능 | Method | Path | 설명 |
|------|--------|------|------|
| 추출 결과 | GET | `/api/v1/extraction/documents/{docId}/ontology-result` | 추출된 개체/관계 |
| 개체 승인/거부 | PUT | `/api/v1/extraction/ontology/{entityId}/confirm` | committed / rejected |

- **API 스펙**: Synapse [extraction-api.md](../../../services/synapse/docs/02_api/extraction-api.md) §3.3, §3.4

---

## 7. UX 상태 설계 (에러/빈 상태/로딩)

### 7.1 에러 상태

| 시나리오 | UI 표시 | 액션 |
|---------|---------|------|
| 문서 목록 조회 실패 | ErrorFallback (implementation-guide.md §1.2) | "다시 시도" 버튼 |
| 문서 저장 실패 (409 Conflict) | 토스트: "다른 사용자가 수정했습니다. 새로고침 후 다시 시도하세요." | 최신 버전 로드 |
| 리뷰 요청 실패 | 토스트 에러 + 상태 유지 (draft) | 재시도 |
| 코멘트 추가 실패 | AddCommentForm에 인라인 에러 | 재시도 |
| Diff 조회 실패 | DiffViewer 영역에 에러 + "다시 시도" | 캐시 무효화 |
| 승인/반려 실패 | 토스트 에러 + 버튼 재활성화 | 재시도 |

### 7.2 빈 상태

| 시나리오 | UI 표시 |
|---------|---------|
| 문서 없음 (케이스 내) | EmptyState: 📄 아이콘 + "이 케이스에 문서가 없습니다" + [+ 새 문서] + [AI 생성 요청] 버튼 |
| 코멘트 없음 | ReviewPanel: "아직 코멘트가 없습니다. 줄을 선택하여 코멘트를 추가하세요." |
| 버전 히스토리 없음 | "(현재 버전만 존재합니다)" |
| 검색 결과 없음 | "'{query}'에 해당하는 문서가 없습니다." |

### 7.3 로딩 상태

| 시나리오 | UI 표시 |
|---------|---------|
| 문서 목록 조회 | DataTable Skeleton (헤더 + 5행) |
| 문서 편집기 로드 | MonacoEditor Skeleton (줄번호 영역 + 코드 블록) |
| 리뷰 패널 로드 | ReviewPanel Skeleton (상태 카드 + 코멘트 3개) |
| Diff 뷰어 로드 | Side-by-Side Skeleton (양쪽 동일 블록) |
| 승인/반려 처리 | 버튼 스피너 + 비활성화 |

---

## 8. 역할별 접근 제어 (RBAC)

### 8.1 기능별 역할 권한

문서 관리는 케이스 스코프 기능이므로, 시스템 역할과 케이스 역할이 모두 적용된다.

**시스템 역할 기반**:

| 기능 | 필요 권한 | admin | manager | attorney | analyst | engineer | staff | viewer |
|------|----------|:-----:|:-------:|:--------:|:-------:|:--------:|:-----:|:------:|
| 문서 목록/상세 조회 | `case:read` | O | O | O | O | O | O | O |
| 문서 생성/수정 | `case:write` | O | O | O | X | X | X | X |
| AI 문서 생성 요청 | `case:write` + `agent:chat` | O | O | O | X | X | X | X |
| 리뷰 요청 제출 | `case:write` | O | O | O | X | X | X | X |
| 코멘트 추가 | `case:read` | O | O | O | O | X | O | X |
| 승인/반려 | `process:approve` | O | O | X | X | X | X | X |
| 수정 요청 (Request Changes) | `process:approve` | O | O | X | X | X | X | X |

**케이스 역할 기반** (시스템 역할과 AND 조건):

| 케이스 역할 | 문서 조회 | 문서 편집 | 코멘트 | 승인/반려 |
|------------|:--------:|:--------:|:------:|:--------:|
| trustee | O | O | O | X* |
| reviewer | O | X | O | O |
| viewer | O | X | X | X |

`*` trustee는 문서 작성자이므로 자신의 문서를 승인할 수 없다 (4-eyes 원칙)

### 8.2 프론트엔드 가드

```typescript
// ApprovalWorkflow 컴포넌트 — process:approve 권한 + reviewer 케이스 역할 필요
const { hasPermission } = usePermission();
const { caseRole } = useCaseRole(caseId);
const canApprove = hasPermission('process:approve') || caseRole === 'reviewer';
const canEdit = hasPermission('case:write') && caseRole !== 'viewer';

{canApprove && (
  <>
    <ApprovalButton />
    <RejectButton />
    <RequestChangesButton />
  </>
)}

{canEdit && <Button onClick={saveDocument}>저장</Button>}
```

> **4-eyes 원칙**: 문서 작성자(author)가 자신의 문서를 승인할 수 없도록 백엔드에서 검증한다. 프론트엔드에서는 현재 사용자가 문서 작성자인 경우 승인 버튼을 비활성화한다.
> **SSOT**: `services/core/docs/07_security/auth-model.md` §2.2, §2.3

---

## 9. K-AIR 전환 노트

| K-AIR (Memento 서비스) | Canvas |
|------------------------|--------|
| 문서 편집: 자체 에디터 | Monaco Editor (react-monaco-editor) |
| Diff: 없음 | react-diff-viewer-continued |
| 리뷰: 단순 승인/반려 | 인라인 코멘트 + 쓰레드 |
| 버전: 수동 관리 | Core API 자동 버저닝 |
| AI 생성 표시: 없음 | AiGeneratedBadge 명시적 표시 |

---

## 결정 사항 (Decisions)

- Monaco Editor 사용 (업무 문서에 구문 강조 + 줄번호 필수)
- Diff 뷰어는 Side-by-Side 기본, Unified 뷰 옵션 제공
- HITL 코멘트는 줄 범위 지정 가능 (단일 줄이 아닌 범위)

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 2.1 | Axiom Team | RBAC 역할별 접근 제어(§8) 추가 |
| 2026-02-20 | 2.0 | Axiom Team | API 연동(§6), UX 상태 설계(§7) 추가 |
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
