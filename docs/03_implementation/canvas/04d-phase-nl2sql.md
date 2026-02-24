# NL2SQL 단계별 구현 계획 (Phase 1~5)

> **상위 문서**: [04d_nl2sql-ontology-gap-analysis.md](04d_nl2sql-ontology-gap-analysis.md)
> **대상**: 73개 NL2SQL 갭 항목 (A1~H10) 해결

---

## Phase 1: 긴급 수정 (런타임 버그·보안)

**해결 항목**: F3, F5, E2, E4

### P1-1: Pie Chart Config 키 불일치 수정 (F3)

**문제**: BE `visualize.py`는 pie chart에 `label_column`/`value_column` 반환하나, FE `ChartRecommender.tsx`는 `x_column`으로 접근
**수정 파일**: `apps/canvas/src/pages/nl2sql/components/ChartRecommender.tsx`
**작업**: pie chart 분기에서 `config.label_column` / `config.value_column` 키 사용

### P1-2: Scatter Chart 타입 처리 (F5)

**문제**: `ChartType`에 'scatter' 포함되나 BE/FE 모두 렌더링 없음
**수정 파일**:
- `services/oracle/app/core/visualize.py` — scatter 추천 규칙 추가 (2 numeric columns)
- `apps/canvas/src/pages/nl2sql/components/ChartRecommender.tsx` — Recharts ScatterChart 렌더링

### P1-3: NL2SQL 라우트 RoleGuard 적용 (E2)

**문제**: `routeConfig.tsx:80`에 RoleGuard 없음. 모든 사용자가 NL2SQL 접근 가능
**수정 파일**: `apps/canvas/src/lib/routes/routeConfig.tsx`
**작업**: nl2sql 라우트에 `<RoleGuard allowedRoles={['admin','manager','attorney','analyst','engineer']}>` 래핑

### P1-4: Rate Limit 429 핸들링 (E4)

**문제**: BE rate limiting 동작하나 FE에서 429 응답 처리 없음
**수정 파일**: `apps/canvas/src/features/nl2sql/api/oracleNl2sqlApi.ts`
**작업**: 429 응답 시 "요청이 너무 많습니다. 잠시 후 다시 시도해주세요" toast 표시 + 재시도 가이드

### Phase 1 수정 파일 요약

| 파일 | 변경 |
| --- | --- |
| `apps/canvas/src/pages/nl2sql/components/ChartRecommender.tsx` | MODIFY (F3, F5) |
| `services/oracle/app/core/visualize.py` | MODIFY (F5) |
| `apps/canvas/src/lib/routes/routeConfig.tsx` | MODIFY (E2) |
| `apps/canvas/src/features/nl2sql/api/oracleNl2sqlApi.ts` | MODIFY (E4) |

### Gate 1 판정 기준

- [x] Pie chart 데이터 정확히 렌더링됨 (label_column/value_column 매핑)
- [x] Scatter chart 2개 numeric 컬럼 결과에서 렌더링됨
- [x] 비인가 사용자 `/analysis/nl2sql` 접근 시 403 리다이렉트
- [x] 429 에러 시 toast 메시지 표시 + 재시도 안내

---

## Phase 2: 핵심 기능 완성

**해결 항목**: G1, G4-G7, G10, G15, A8, B2

### P2-1: DatasourceSelector 구현 (G1, B2)

**문제**: `Nl2SqlPage.tsx:11`에 `DEFAULT_DATASOURCE='ds_business_main'` 하드코딩
**작업**:
- Meta API 호출: `GET /text2sql/meta/datasources` → 데이터소스 목록 로드
- Shadcn `Select` 컴포넌트로 드롭다운 구현
- 선택값을 `postAsk()`/`postReactStream()`에 전달

**수정 파일**:
- `apps/canvas/src/pages/nl2sql/Nl2SqlPage.tsx` — MODIFY (하드코딩 제거)
- `apps/canvas/src/features/nl2sql/api/oracleNl2sqlApi.ts` — MODIFY (getDatasources 추가)

### P2-2: Meta API FE 통합 (A8)

**작업**: `oracleNl2sqlApi.ts`에 Meta API 함수 추가
- `getTables(datasourceId, search?, page?)` → `GET /text2sql/meta/tables`
- `getTableColumns(tableName, datasourceId)` → `GET /text2sql/meta/tables/{name}/columns`
- `getDatasources()` → `GET /text2sql/meta/datasources`

### P2-3: Chat UI 실 API 연동 (G4-G6)

**문제**: MessageBubble, SqlPreview, ThinkingIndicator 존재하나 Nl2SqlPage에서 직접 div 렌더링
**작업**: 기존 컴포넌트를 Nl2SqlPage의 메시지 렌더링에 연결

**수정 파일**: `apps/canvas/src/pages/nl2sql/Nl2SqlPage.tsx` — MODIFY (컴포넌트 통합)

### P2-4: SQL Editor (Monaco) 통합 (G7)

**문제**: react-monaco-editor 의존성 있으나 NL2SQL에서 미사용
**작업**: SqlPreview 컴포넌트에 "수정" 모드 토글 → Monaco Editor 표시 → 수정된 SQL 재실행

**수정 파일**: `apps/canvas/src/pages/nl2sql/components/SqlPreview.tsx` — MODIFY

### P2-5: Streaming Progress UI (G10)

**문제**: ThinkingIndicator만 (단계별 타임라인 없음)
**작업**: SyncProgress 패턴 참조하여 ReAct 9-step 타임라인 구현
- select → generate → validate → fix → execute → quality → triage → result

**수정 파일**: `apps/canvas/src/pages/nl2sql/components/` — CREATE (ReactProgressTimeline.tsx)

### P2-6: Result Table 개선 (G15)

**문제**: 결과를 기본 div로 표시. DataTable 미사용
**작업**: 기존 `DataTable` 컴포넌트 재사용하여 정렬/페이지네이션 지원

**수정 파일**: `apps/canvas/src/pages/nl2sql/Nl2SqlPage.tsx` — MODIFY

### Phase 2 수정 파일 요약

| 파일 | 변경 |
| --- | --- |
| `apps/canvas/src/pages/nl2sql/Nl2SqlPage.tsx` | MODIFY (G1, B2, G4-G6, G15) |
| `apps/canvas/src/features/nl2sql/api/oracleNl2sqlApi.ts` | MODIFY (A8) |
| `apps/canvas/src/pages/nl2sql/components/SqlPreview.tsx` | MODIFY (G7) |
| `apps/canvas/src/pages/nl2sql/components/ReactProgressTimeline.tsx` | CREATE (G10) |

### Gate 2 판정 기준

- [x] DatasourceSelector 드롭다운에서 데이터소스 선택 가능
- [x] 선택한 데이터소스로 `/text2sql/ask` 호출 성공
- [x] MessageBubble에 사용자/어시스턴트 메시지 표시
- [x] SqlPreview에서 SQL 복사 + Monaco Editor 편집 모드 전환
- [x] ReAct 모드에서 단계별 타임라인 진행률 표시
- [x] 결과 테이블 정렬/페이지네이션 동작
- [x] Meta API 호출: /meta/tables 200 응답

---

## Phase 3: UX 고도화

**해결 항목**: G3, G8, G9, G11-G14, D4, C6

### P3-1: Empty State (G3)

**작업**: 기존 `EmptyState` 컴포넌트 재사용. 초기 화면에 "질문을 입력하세요" 안내

### P3-2: CSV/Excel Export (G9)

**작업**: DataTable 하단에 "CSV 다운로드" / "Excel 다운로드" 버튼

### P3-3: Chart/Table/SQL 탭 전환 (G11)

**작업**: 기존 `ChartSwitcher` 패턴 참조. 결과 영역을 탭으로 분리 (차트 / 테이블 / SQL)

### P3-4: Error Boundary (G12) + Network Retry (G13)

**작업**:
- `ErrorState` 컴포넌트로 NL2SQL 페이지 래핑
- 네트워크 에러 시 "재시도" 버튼

### P3-5: Multi-turn Context (G14)

**작업**: 이전 대화 맥락(question+sql 쌍)을 API request body의 `context` 필드에 포함

### P3-6: LLM Summary 표시 (C6)

**작업**: `data.summary` 응답을 결과 섹션 상단에 요약 텍스트로 표시

### P3-7: ReAct 타임라인 고도화 (D4)

**작업**: P2의 ReactProgressTimeline에 경과 시간, iteration 번호, triage 결과(COMPLETE/CONTINUE/FAIL) 표시

### Phase 3 수정 파일 요약

| 파일 | 변경 |
| --- | --- |
| `apps/canvas/src/pages/nl2sql/Nl2SqlPage.tsx` | MODIFY (G3, G9, G11, C6, G14) |
| `apps/canvas/src/pages/nl2sql/components/ResultPanel.tsx` | CREATE (G11 탭 분리) |
| `apps/canvas/src/pages/nl2sql/components/ReactProgressTimeline.tsx` | MODIFY (D4) |

### Gate 3 판정 기준

- [x] 초기 빈 화면에 EmptyState 안내 표시
- [x] "CSV 다운로드" 버튼 → 올바른 CSV 파일 생성
- [x] 차트/테이블/SQL 탭 전환 정상 동작
- [x] 네트워크 에러 시 ErrorState + "재시도" 버튼
- [x] 연속 질문 시 이전 맥락이 API에 포함됨 (request body 확인)
- [x] LLM summary가 결과 상단에 표시됨
- [x] ReAct 타임라인에 iteration 번호 + triage 결과 표시

---

## Phase 4: 고급 기능

**해결 항목**: B7, C5(kpi_card), C7-C12, E5

### P4-1: Direct SQL Admin UI (B7, E5)

**작업**: Admin 전용 페이지 또는 모달에서 raw SQL 입력 → `POST /text2sql/direct-sql` 실행

### P4-2: KPI Card 렌더링 (C5 나머지)

**작업**: ChartRecommender에 kpi_card 타입 렌더링 추가 (대형 숫자 + 라벨)

### P4-3: Metadata 패널 (C7-C12)

**작업**: 결과 하단 접이식 패널에 실행 시간, Guard 상태, 사용 테이블 등 메타데이터 표시

### P4-4: Row Limit 설정 (B5)

**작업**: 옵션 패널에 row_limit 슬라이더 (100 ~ 10000)

### Phase 4 수정 파일 요약

| 파일 | 변경 |
| --- | --- |
| `apps/canvas/src/pages/nl2sql/components/DirectSqlPanel.tsx` | CREATE (B7) |
| `apps/canvas/src/pages/nl2sql/components/ChartRecommender.tsx` | MODIFY (kpi_card) |
| `apps/canvas/src/pages/nl2sql/components/MetadataPanel.tsx` | CREATE (C7-C12) |
| `apps/canvas/src/pages/nl2sql/Nl2SqlPage.tsx` | MODIFY (B5, 통합) |

### Gate 4 판정 기준

- [x] Admin 사용자 direct-sql 실행 성공
- [x] 비 admin 사용자 direct-sql 접근 차단
- [x] KPI Card (단일 숫자 결과) 올바르게 렌더링
- [x] 메타데이터 패널에 execution_time_ms, guard_status 등 표시
- [x] row_limit 변경 후 요청에 반영됨

---

## Phase 5: 품질·문서 동기화

**해결 항목**: A1, A2, A5, B1, E3, C1, C13, C15

### P5-1: API Prefix 정규화 (A1, A5)

**검토**: 설계 문서의 `/api/v1` prefix 적용 여부 결정. 적용 시 BE router prefix 변경 + FE API base URL 변경

### P5-2: FE 요청 검증 강화 (B1)

**작업**: nl2sqlFormSchema에 `max(2000)` 제한 추가

### P5-3: Tenant Isolation 확인 (E3)

**작업**: API 클라이언트에 X-Tenant-Id 헤더 자동 주입 확인 및 보완

### P5-4: Response Wrapper 점검 (C1, C13, C15)

**작업**: FE에서 `response.success` 체크 추가, error.code별 한글 메시지 매핑

### P5-5: 설계 문서-코드 동기화

**작업**: 갭 분석 기반으로 설계 문서(text2sql-api.md, nl2sql-chat.md) 현행화

### Phase 5 수정 파일 요약

| 파일 | 변경 |
| --- | --- |
| `apps/canvas/src/pages/nl2sql/nl2sqlFormSchema.ts` | MODIFY (B1) |
| `apps/canvas/src/features/nl2sql/api/oracleNl2sqlApi.ts` | MODIFY (C1, C13, C15) |
| `apps/canvas/src/lib/api/clients.ts` | VERIFY (E3) |
| `services/oracle/docs/02_api/text2sql-api.md` | UPDATE (문서 동기화) |
| `apps/canvas/docs/04_frontend/nl2sql-chat.md` | UPDATE (문서 동기화) |

### Gate 5 판정 기준

- [x] FE에서 question 2000자 초과 시 유효성 에러 표시
- [x] response.success === false 시 에러 UI 표시
- [x] error.code별 한글 메시지 매핑 (최소 5개 코드)
- [ ] 설계 문서에 현재 구현 상태 반영 완료 → text2sql-api.md/nl2sql-chat.md 현행화 잔여
