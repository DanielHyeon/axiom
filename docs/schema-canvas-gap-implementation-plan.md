# Schema Canvas Gap 구현 계획서 (G1-G8)

> ADR-033 (Text2SQL Unified Schema Navigation) 갭 분석 결과 도출된 8개 미비 기능의 상세 구현 계획

**문서 버전**: 1.0
**작성일**: 2026-03-21
**스펙 참조**: `docs/text2sql-unified-spec.md`, ADR-033

---

## 1. 개요

### 1.1 목적

ADR-033에서 KAIR 레퍼런스 프로젝트와 비교 분석한 결과 확인된 8개 미비 기능(G1~G8)을 Axiom Schema Canvas에 구현하기 위한 상세 기술 계획을 수립한다.

### 1.2 범위

| 구분 | Gap ID | 기능명 | 우선순위 |
|------|--------|--------|----------|
| Core | G1 | FK 가시성 토글 (소스별) | P1 |
| Core | G2 | 사용자 관계 편집 모달 (CardinalityModal) | P1 |
| Core | G3 | 스키마 편집 API 연동 (프론트엔드) | P1 |
| Core | G4 | Neo4j 관계 column_pairs 구조 | P1 |
| Enhancement | G5 | 실시간 캔버스 업데이트 | P2 |
| Enhancement | G6 | 시맨틱 검색 (벡터 기반) | P2 |
| Enhancement | G7 | 논리명/물리명 토글 | P2 |
| Enhancement | G8 | 테이블 데이터 프리뷰 패널 | P2 |

### 1.3 기존 구현 현황

현재 Axiom에 이미 구현된 관련 인프라:

- **백엔드**: `services/synapse/app/api/schema_edit.py` -- 테이블/컬럼 설명 수정, 관계 CRUD, 임베딩 재생성 API 완비
- **백엔드**: `services/synapse/app/api/schema_navigation.py` -- 가용성 조회, 관련 테이블 탐색 API
- **백엔드**: `services/synapse/app/api/graph.py` -- 벡터 검색 API (`POST /api/v3/synapse/graph/vector-search`)
- **프론트엔드**: `canvas/src/features/nl2sql/components/SchemaCanvas.tsx` -- Mermaid 기반 ERD 캔버스
- **프론트엔드**: `canvas/src/features/nl2sql/components/RelationshipManager.tsx` -- FK 관계 편집 UI (로컬 상태만)
- **프론트엔드**: `canvas/src/features/nl2sql/components/SchemaSearchBar.tsx` -- 텍스트 기반 검색
- **프론트엔드**: `canvas/src/shared/api/schemaNavigationApi.ts` -- Synapse schema-nav API 클라이언트
- **공통 타입**: `canvas/src/shared/types/schemaNavigation.ts`, `canvas/src/features/nl2sql/types/schema.ts`

---

## 2. 의존 관계 분석

### 2.1 의존 관계 다이어그램

```
                    G4 (column_pairs 구조)
                   / |
                  /  |
                 v   v
    G1 (FK 가시성)   G3 (스키마 편집 API 연동)
         |               |
         v               v
    G2 (관계 편집 모달)  G7 (논리명 토글)
                          |
                          v
                    G5 (실시간 업데이트)

    G6 (시맨틱 검색) ── 독립
    G8 (데이터 프리뷰) ── 독립
```

### 2.2 의존 관계 상세

| Gap | 선행 의존 | 이유 |
|-----|-----------|------|
| G4 | 없음 | column_pairs는 전체 FK 데이터 구조의 기반 |
| G3 | G4 | 편집 API 연동 시 column_pairs 구조로 관계를 관리해야 함 |
| G1 | G4 | FK 가시성 토글은 관계 소스(source) 정보가 column_pairs에 포함되어야 함 |
| G2 | G1, G3 | 관계 편집 모달은 FK 가시성(G1)과 API 연동(G3)에 의존 |
| G7 | G3 | 논리명은 description 필드 — 편집 API가 연동되어야 의미 있음 |
| G5 | G3, G7 | 실시간 업데이트는 편집 결과를 캔버스에 반영하는 것이므로 G3/G7 이후 |
| G6 | 없음 | 기존 벡터 검색 API 활용, 독립 구현 가능 |
| G8 | 없음 | Oracle text2sql API 활용, 독립 구현 가능 |

### 2.3 구현 순서 결정 근거

1. **Phase 1 (G4 + G3)**: column_pairs 데이터 구조가 캔버스 전반의 기반이 되므로 최우선. G3의 API 클라이언트는 G2/G5 등 후속 기능에서 재사용.
2. **Phase 2 (G1 + G2)**: G4의 소스 구분 데이터를 활용한 핵심 UX. G1과 G2는 FK 관계 표시/편집의 양면.
3. **Phase 3 (G7 + G5)**: 편집 결과를 캔버스에 반영하는 개선 기능. G7은 간단, G5는 중간 복잡도.
4. **Phase 4 (G6 + G8)**: 독립 부가 기능. 기존 API 활용으로 구현 부담 낮음.

---

## 3. 구현 단계 (Phase별)

### Phase 1: 기반 인프라 (G4 + G3)

**목표**: FK 관계의 column_pairs 데이터 구조 확립 + 스키마 편집 API 프론트엔드 연동

```
G4: column_pairs 타입 정의 → Neo4j 쿼리 수정 → 프론트엔드 타입 동기화
                                                         |
G3: API 클라이언트 생성 → useSchemaEdit 훅 → 인라인 편집 UI
```

**병렬 가능 작업**:
- G4 백엔드(Neo4j 쿼리)와 G3 API 클라이언트는 동시 진행 가능
- G4 프론트엔드 타입 정의 완료 후 G3의 UI 작업 시작

### Phase 2: 핵심 UX (G1 + G2)

**목표**: FK 관계선의 소스별 가시성 토글 + 사용자 관계 편집 모달

```
G1: fkVisibility 상태 → Mermaid 클래스 분기 → 토글 버튼 UI
                                                    |
G2: CardinalityModal 컴포넌트 → G3의 API 훅 연동 → 캔버스 업데이트
```

**병렬 가능 작업**:
- G1의 상태/UI와 G2의 모달 컴포넌트는 동시 진행 가능

### Phase 3: 개선 (G7 + G5)

**목표**: 논리명/물리명 전환 + 실시간 캔버스 갱신

```
G7: displayMode 상태 → ERD 렌더링 분기 → 토글 버튼
                                              |
G5: 폴링/SSE 설계 → handleCanvasUpdate → 디바운스 적용
```

**병렬 가능 작업**:
- G7은 프론트엔드 전용이므로 G5의 백엔드 변경 사항 없이 병렬 진행

### Phase 4: 부가 기능 (G6 + G8)

**목표**: 시맨틱 검색 모드 추가 + 테이블 데이터 프리뷰 패널

```
G6: SchemaSearchBar에 시맨틱 모드 토글 → 벡터 검색 API 호출 → 결과 정렬
                                                                    |
G8: DataPreviewPanel 컴포넌트 → Oracle API 호출 → 슬라이드 패널 UI
```

**병렬 가능 작업**: G6과 G8은 완전히 독립적으로 병렬 진행 가능

---

## 4. 각 Gap별 상세 구현 계획

---

### G4: Neo4j 관계 column_pairs 구조

**What**: 같은 테이블 쌍 간에 복수의 FK 컬럼 매핑을 `column_pairs` 배열로 관리. 현재 `RelatedTableItem`의 `sourceColumns`/`targetColumns`는 단순 배열이며, 어떤 소스 컬럼이 어떤 타겟 컬럼에 매핑되는지 쌍(pair) 정보가 없다.

**Where**:
- 수정: `services/synapse/app/services/related_tables_service.py` -- `RelatedTableItem` 모델에 `column_pairs` 필드 추가
- 수정: `canvas/src/shared/types/schemaNavigation.ts` -- `ColumnPair` 타입 및 `RelatedTableItem.columnPairs` 추가
- 수정: `canvas/src/features/nl2sql/types/schema.ts` -- `SchemaRelationship`에 `columnPairs` 필드 추가
- 수정: `canvas/src/features/datasource/utils/mermaidCodeGen.ts` -- `extractRelations()`에서 column_pairs 기반 관계선 생성
- 수정: `canvas/src/features/nl2sql/components/SchemaCanvas.tsx` -- ERD 변환 시 column_pairs 반영

**How**:

1) 백엔드: `RelatedTableItem` Pydantic 모델에 `column_pairs` 필드 추가

```python
# services/synapse/app/services/related_tables_service.py

class ColumnPair(BaseModel):
    """FK 컬럼 매핑 한 쌍"""
    model_config = ConfigDict(populate_by_name=True)
    source_column: str = Field(alias="sourceColumn")
    target_column: str = Field(alias="targetColumn")

class RelatedTableItem(BaseModel):
    # ... 기존 필드 유지 ...
    column_pairs: list[ColumnPair] = Field(default_factory=list, alias="columnPairs")
```

2) `_row_to_item()` 헬퍼에서 `source_cols`/`target_cols`를 zip하여 `column_pairs` 생성

```python
def _row_to_item(row, mode, relation_type, base_score, ...):
    src_cols = row.get("source_cols") or []
    tgt_cols = row.get("target_cols") or []
    pairs = [
        ColumnPair(source_column=s, target_column=t)
        for s, t in zip(src_cols, tgt_cols)
    ]
    return RelatedTableItem(
        # ... 기존 필드 ...
        column_pairs=pairs,
    )
```

3) 프론트엔드: `schemaNavigation.ts` 타입에 `ColumnPair` 인터페이스 추가

```typescript
export interface ColumnPair {
  sourceColumn: string;
  targetColumn: string;
}

export interface RelatedTableItem {
  // ... 기존 필드 유지 ...
  columnPairs: ColumnPair[];  // 신규
}
```

4) `SchemaRelationship` 타입에 `columnPairs` 옵션 필드 추가

```typescript
export interface SchemaRelationship {
  // ... 기존 필드 유지 ...
  columnPairs?: ColumnPair[];  // 복수 매핑 지원
}
```

5) `mermaidCodeGen.ts`의 `extractRelations()` -- column_pairs가 있으면 각 pair마다 개별 관계선 생성

**Dependencies**: 없음 (기반 작업)

**Validation**:
- 단위 테스트: `_row_to_item()`에 source_cols=[a,b], target_cols=[x,y] 전달 시 column_pairs 길이 2 확인
- 통합 테스트: related-tables API 응답에 `columnPairs` 필드 존재 확인
- 프론트엔드: ERD에 복수 FK 관계선이 올바르게 렌더링되는지 확인

**Complexity**: Medium
**Estimated files**: 수정 5

---

### G3: 스키마 편집 API 연동 (프론트엔드)

**What**: 기존 Synapse `schema_edit.py` 엔드포인트와 연동하는 프론트엔드 API 클라이언트 + 인라인 편집 UI. 현재 `RelationshipManager`는 로컬 상태만 관리하며 백엔드 API에 연결되어 있지 않다.

**Where**:
- 신규: `canvas/src/shared/api/schemaEditApi.ts` -- Synapse schema-edit API 클라이언트
- 신규: `canvas/src/features/nl2sql/hooks/useSchemaEdit.ts` -- TanStack Query 기반 CRUD 훅
- 수정: `canvas/src/features/nl2sql/components/RelationshipManager.tsx` -- API 연동
- 수정: `canvas/src/features/nl2sql/components/TableDetailPanel.tsx` -- 인라인 설명 편집 UI
- 수정: `canvas/src/features/nl2sql/components/ColumnDetailPanel.tsx` -- 컬럼 설명 인라인 편집

**How**:

1) API 클라이언트 생성 (`schemaEditApi.ts`):

```typescript
// canvas/src/shared/api/schemaEditApi.ts
import { synapseApi } from '@/lib/api/clients';

const BASE = '/api/v3/synapse/schema-edit';

/** 테이블 설명 수정 */
export async function updateTableDescription(tableName: string, description: string) {
  const res = await synapseApi.put(`${BASE}/tables/${tableName}/description`, { description });
  return (res as any).data;
}

/** 컬럼 설명 수정 */
export async function updateColumnDescription(tableName: string, columnName: string, description: string) {
  const res = await synapseApi.put(`${BASE}/columns/${tableName}/${columnName}/description`, { description });
  return (res as any).data;
}

/** 관계 목록 조회 */
export async function listRelationships() {
  const res = await synapseApi.get(`${BASE}/relationships`);
  return (res as any).data;
}

/** 관계 추가 */
export async function createRelationship(payload: {
  source_table: string;
  source_column: string;
  target_table: string;
  target_column: string;
  relationship_type?: string;
  description?: string;
}) {
  const res = await synapseApi.post(`${BASE}/relationships`, payload);
  return (res as any).data;
}

/** 관계 삭제 */
export async function deleteRelationship(relId: string) {
  const res = await synapseApi.delete(`${BASE}/relationships/${relId}`);
  return (res as any).data;
}

/** 테이블 임베딩 재생성 */
export async function rebuildTableEmbedding(tableName: string) {
  const res = await synapseApi.post(`${BASE}/tables/${tableName}/embedding`);
  return (res as any).data;
}
```

2) TanStack Query 훅 (`useSchemaEdit.ts`):

```typescript
// canvas/src/features/nl2sql/hooks/useSchemaEdit.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as schemaEditApi from '@/shared/api/schemaEditApi';

export function useSchemaEdit() {
  const qc = useQueryClient();

  // 관계 목록 조회
  const relationships = useQuery({
    queryKey: ['schema-edit', 'relationships'],
    queryFn: schemaEditApi.listRelationships,
    staleTime: 2 * 60 * 1000,
  });

  // 테이블 설명 수정
  const updateTableDesc = useMutation({
    mutationFn: (p: { tableName: string; description: string }) =>
      schemaEditApi.updateTableDescription(p.tableName, p.description),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schema-edit'] }),
  });

  // 컬럼 설명 수정
  const updateColumnDesc = useMutation({
    mutationFn: (p: { tableName: string; columnName: string; description: string }) =>
      schemaEditApi.updateColumnDescription(p.tableName, p.columnName, p.description),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schema-edit'] }),
  });

  // 관계 추가
  const createRel = useMutation({
    mutationFn: schemaEditApi.createRelationship,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schema-edit', 'relationships'] }),
  });

  // 관계 삭제
  const deleteRel = useMutation({
    mutationFn: schemaEditApi.deleteRelationship,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schema-edit', 'relationships'] }),
  });

  return { relationships, updateTableDesc, updateColumnDesc, createRel, deleteRel };
}
```

3) `RelationshipManager.tsx` 수정: `onAdd`에서 `createRel.mutate()` 호출, `onRemove`에서 `deleteRel.mutate()` 호출하도록 상위 컴포넌트에서 훅 연결

4) `TableDetailPanel.tsx`에 인라인 편집 UI 추가: description 필드 옆에 편집 아이콘, 클릭 시 `<input>` 전환, blur/Enter 시 `updateTableDesc.mutate()` 호출

5) `ColumnDetailPanel.tsx` 동일 패턴 적용

**Dependencies**: G4 (column_pairs 구조가 확정되어야 관계 추가 시 올바른 데이터 전송 가능)

**Validation**:
- 단위 테스트: `useSchemaEdit` 훅의 각 mutation이 올바른 API 엔드포인트 호출 확인 (MSW mock)
- 통합 테스트: 테이블 설명 편집 → 임베딩 재생성 완료 확인
- E2E: RelationshipManager에서 관계 추가 → 목록에 반영, 삭제 → 목록에서 제거

**Complexity**: Medium
**Estimated files**: 신규 2, 수정 3

---

### G1: FK 가시성 토글 (소스별)

**What**: ERD 관계선을 FK 소스 타입별(DDL, User, Fabric)로 색상/스타일 구분하고, 토글 버튼으로 소스별 on/off 제어. 프론트엔드 전용 기능.

**Where**:
- 신규: `canvas/src/features/nl2sql/components/FkVisibilityToolbar.tsx` -- 소스별 토글 버튼 UI
- 신규: `canvas/src/features/nl2sql/hooks/useFkVisibility.ts` -- 가시성 상태 관리 훅
- 수정: `canvas/src/features/nl2sql/types/schema.ts` -- `FkSource` 타입, `SchemaRelationship`에 `source` 필드 추가
- 수정: `canvas/src/features/datasource/utils/mermaidCodeGen.ts` -- 소스별 Mermaid 클래스 적용
- 수정: `canvas/src/features/nl2sql/components/SchemaCanvas.tsx` -- 가시성 필터 + 툴바 통합

**How**:

1) FK 소스 타입 정의:

```typescript
// canvas/src/features/nl2sql/types/schema.ts에 추가
export type FkSource = 'ddl' | 'user' | 'fabric';

export interface SchemaRelationship {
  // ... 기존 필드 ...
  source?: FkSource;  // 관계 소스 식별
}
```

2) 가시성 상태 훅 (`useFkVisibility.ts`):

```typescript
// canvas/src/features/nl2sql/hooks/useFkVisibility.ts
import { useState, useCallback } from 'react';
import type { FkSource } from '../types/schema';

export interface FkVisibilityState {
  ddl: boolean;    // DDL 기반 FK (초록 실선)
  user: boolean;   // 사용자 추가 FK (주황 실선)
  fabric: boolean; // Fabric 추론 FK (파랑 점선)
}

const DEFAULT_VISIBILITY: FkVisibilityState = { ddl: true, user: true, fabric: true };

export function useFkVisibility() {
  const [visibility, setVisibility] = useState<FkVisibilityState>(DEFAULT_VISIBILITY);

  const toggle = useCallback((source: FkSource) => {
    setVisibility((prev) => ({ ...prev, [source]: !prev[source] }));
  }, []);

  const isVisible = useCallback(
    (source: FkSource | undefined) => {
      if (!source) return visibility.ddl; // 소스 미지정 시 DDL로 간주
      return visibility[source];
    },
    [visibility],
  );

  return { visibility, toggle, isVisible };
}
```

3) 소스별 스타일 정의:

| 소스 | 색상 | 선 스타일 | Mermaid 표기 |
|------|------|-----------|-------------|
| DDL | `#22C55E` (초록) | 실선 | 기본 관계선 |
| User | `#F97316` (주황) | 실선 | `%%{init: {'theme': 'base'}}%%` + CSS 클래스 |
| Fabric | `#3B82F6` (파랑) | 점선 | 점선 관계선 `..` |

4) `mermaidCodeGen.ts` 수정: `generateMermaidERCode()`에 `visibleSources` 필터 파라미터 추가. 관계 렌더링 시 `source` 필드에 따라 Mermaid 관계선 스타일 분기:

```typescript
// 관계선 렌더링 시 소스별 분기
for (const rel of relations) {
  if (!visibleSources.has(rel.source ?? 'ddl')) continue;
  const from = sanitizeTableName(rel.fromTable);
  const to = sanitizeTableName(rel.toTable);
  if (rel.source === 'fabric') {
    lines.push(`    ${from} ..o--|| ${to} : "${rel.fromColumn}"`);
  } else {
    lines.push(`    ${from} }o--|| ${to} : "${rel.fromColumn}"`);
  }
}
```

5) `FkVisibilityToolbar.tsx` -- 3개의 토글 칩(DDL/User/Fabric) + 색상 인디케이터

6) `SchemaCanvas.tsx` 상단 바에 `FkVisibilityToolbar` 통합

**Dependencies**: G4 (column_pairs에 소스 정보 포함)

**Validation**:
- 단위 테스트: `useFkVisibility` 훅의 토글/isVisible 로직
- 시각 테스트: DDL=초록 실선, User=주황 실선, Fabric=파랑 점선 구분 확인
- 토글 테스트: 특정 소스 off 시 해당 관계선 비표시 확인

**Complexity**: Medium
**Estimated files**: 신규 2, 수정 3

---

### G2: 사용자 관계 편집 모달 (CardinalityModal)

**What**: 테이블 간 FK 관계를 사용자가 수동으로 추가/편집하는 모달 다이얼로그. Cardinality 선택(many_to_one, one_to_one 등) + 소스/타겟 테이블-컬럼 매핑 UI. 기존 `RelationshipManager` 인라인 폼을 모달로 확장.

**Where**:
- 신규: `canvas/src/features/nl2sql/components/CardinalityModal.tsx` -- 모달 컴포넌트
- 수정: `canvas/src/features/nl2sql/components/RelationshipManager.tsx` -- "관계 추가" 버튼이 모달 열기로 변경
- 수정: `canvas/src/features/nl2sql/components/SchemaCanvas.tsx` -- 모달 상태 관리 + ERD 관계선 클릭 시 편집 모달 열기

**How**:

1) `CardinalityModal.tsx` 컴포넌트:

```typescript
// canvas/src/features/nl2sql/components/CardinalityModal.tsx
interface CardinalityModalProps {
  open: boolean;
  onClose: () => void;
  /** 편집 모드: 기존 관계 전달 시 편집, 없으면 신규 생성 */
  editingRelationship?: SchemaRelationship;
  /** 사용 가능한 테이블 목록 */
  tables: CanvasTable[];
  /** 테이블의 컬럼 목록 조회 */
  getColumns: (tableName: string) => ColumnMeta[];
  /** 저장 핸들러 (G3의 useSchemaEdit.createRel 연결) */
  onSave: (rel: CreateRelationshipPayload) => void;
}
```

모달 내부 UI 구성:
- 소스 테이블 + 컬럼 선택 (드롭다운)
- 타겟 테이블 + 컬럼 선택 (드롭다운)
- Cardinality 라디오 그룹: `many_to_one` | `one_to_one` | `one_to_many` | `many_to_many`
- column_pairs 복수 매핑 지원: "매핑 추가" 버튼으로 여러 컬럼 쌍 등록
- 설명 입력 (선택)
- 저장/취소 버튼

2) shadcn/ui `Dialog` 컴포넌트 활용:

```typescript
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
```

3) `RelationshipManager.tsx`의 "관계 추가" 버튼 클릭 시 `CardinalityModal` open

4) 저장 시 `useSchemaEdit().createRel.mutate()` 호출 -- G3에서 만든 훅 활용

5) ERD 관계선 클릭 시 편집 모드로 모달 열기 (editingRelationship prop 전달)

**Dependencies**: G1 (소스 구분), G3 (API 연동 훅)

**Validation**:
- 단위 테스트: 모달 열기/닫기, 폼 유효성 검증 (필수 필드 비어있으면 저장 버튼 비활성)
- 통합 테스트: 모달에서 관계 추가 → API 호출 → 목록 갱신 확인
- UX 테스트: Cardinality 변경 시 ERD 관계선 기호 변경 확인

**Complexity**: High
**Estimated files**: 신규 1, 수정 2

---

### G7: 논리명/물리명 토글

**What**: 캔버스의 테이블/컬럼 표시를 물리명(name) ↔ 논리명(description) 전환하는 토글 기능. 로컬 상태 관리.

**Where**:
- 신규: `canvas/src/features/nl2sql/hooks/useDisplayMode.ts` -- 표시 모드 상태 훅
- 수정: `canvas/src/features/nl2sql/components/SchemaCanvas.tsx` -- 토글 버튼 + ERD 렌더링 분기
- 수정: `canvas/src/features/datasource/utils/mermaidCodeGen.ts` -- `generateMermaidERCode()`에 displayMode 파라미터 추가

**How**:

1) 표시 모드 훅 (`useDisplayMode.ts`):

```typescript
// canvas/src/features/nl2sql/hooks/useDisplayMode.ts
import { useState, useCallback } from 'react';

export type DisplayMode = 'physical' | 'logical';

export function useDisplayMode() {
  const [displayMode, setDisplayMode] = useState<DisplayMode>('physical');

  const toggle = useCallback(() => {
    setDisplayMode((prev) => (prev === 'physical' ? 'logical' : 'physical'));
  }, []);

  return { displayMode, toggle };
}
```

2) `generateMermaidERCode()` 수정: `displayMode` 옵션 추가

```typescript
export function generateMermaidERCode(
  tables: ERDTableInfo[],
  options?: {
    maxColumnsPerTable?: number;
    displayMode?: 'physical' | 'logical';  // 신규
  },
) {
  const mode = options?.displayMode ?? 'physical';
  // ...
  for (const table of enrichedTables) {
    // 논리명 모드: description이 있으면 description 사용, 없으면 name 폴백
    const displayName = mode === 'logical' && table.description
      ? sanitizeTableName(table.description)
      : sanitizeTableName(table.name);
    lines.push(`    ${displayName} {`);
    // 컬럼도 동일 로직 적용
  }
}
```

3) `SchemaCanvas.tsx` 상단 바에 토글 버튼 추가:

```tsx
<button onClick={toggleDisplayMode} className="...">
  {displayMode === 'physical' ? '논리명 보기' : '물리명 보기'}
</button>
```

4) `CanvasTable` 타입 또는 `ERDTableInfo`에 `description` 필드가 이미 존재 (`ERDTableInfo.description?` -- 현재 optional). 테이블 데이터 로드 시 description을 함께 가져오도록 보장.

**Dependencies**: G3 (description 편집 후 최신 값 반영)

**Validation**:
- 단위 테스트: `useDisplayMode` 훅 토글 동작
- 시각 테스트: physical 모드에서 테이블명이 DB 물리명, logical 모드에서 한글 설명 표시
- 엣지 케이스: description이 없는 테이블은 logical 모드에서도 물리명 표시 (폴백)

**Complexity**: Low
**Estimated files**: 신규 1, 수정 2

---

### G5: 실시간 캔버스 업데이트

**What**: Neo4j 스키마 변경(테이블 추가, 컬럼 추가, 설명 수정 등) 시 캔버스를 자동으로 갱신. 폴링 방식으로 구현 (SSE는 Neo4j 네이티브 이벤트 미지원으로 Phase 2에서 고려).

**Where**:
- 신규: `canvas/src/features/nl2sql/hooks/useCanvasSync.ts` -- 폴링 기반 캔버스 동기화 훅
- 수정: `services/synapse/app/api/schema_edit.py` -- 변경 이벤트 타임스탬프 반환 엔드포인트 추가
- 수정: `services/synapse/app/services/schema_edit_service.py` -- 최종 수정 시각 조회 메서드
- 수정: `canvas/src/shared/api/schemaEditApi.ts` -- 변경 감지 API 호출 추가
- 수정: `canvas/src/features/nl2sql/components/SchemaCanvas.tsx` -- sync 훅 통합

**How**:

1) 백엔드: 최종 수정 타임스탬프 조회 엔드포인트 추가

```python
# services/synapse/app/api/schema_edit.py에 추가
@router.get("/last-modified")
async def get_last_modified(request: Request):
    """스키마의 최종 수정 시각을 반환한다 (폴링 최적화)."""
    ts = schema_edit_service.get_last_modified(_tenant(request))
    return {"success": True, "data": {"last_modified": ts}}
```

```python
# services/synapse/app/services/schema_edit_service.py에 추가
def get_last_modified(self, tenant_id: str) -> str | None:
    rows = self._store.list_tables(tenant_id)
    if not rows:
        return None
    return max(row["last_updated"] for row in rows).isoformat() \
        if any(row.get("last_updated") for row in rows) else None
```

2) 프론트엔드: 폴링 훅 (`useCanvasSync.ts`)

```typescript
// canvas/src/features/nl2sql/hooks/useCanvasSync.ts
import { useQuery } from '@tanstack/react-query';
import { useRef, useEffect } from 'react';

export function useCanvasSync(opts: {
  enabled: boolean;
  pollingInterval?: number;  // 기본 10초
  onUpdate: () => void;      // 캔버스 갱신 콜백
}) {
  const lastModifiedRef = useRef<string | null>(null);

  const { data } = useQuery({
    queryKey: ['schema-edit', 'last-modified'],
    queryFn: () => schemaEditApi.getLastModified(),
    enabled: opts.enabled,
    refetchInterval: opts.pollingInterval ?? 10_000,
    staleTime: 0,
  });

  useEffect(() => {
    if (!data?.last_modified) return;
    if (lastModifiedRef.current && data.last_modified !== lastModifiedRef.current) {
      // 변경 감지 -- 디바운스된 캔버스 갱신
      opts.onUpdate();
    }
    lastModifiedRef.current = data.last_modified;
  }, [data?.last_modified]);
}
```

3) `SchemaCanvas.tsx`에서 `useCanvasSync` 통합: `onUpdate` 콜백에서 TanStack Query 캐시 무효화 → ERD 재렌더링

**Dependencies**: G3 (편집 API가 동작해야 변경 이벤트 발생), G7 (논리명 갱신도 반영)

**Validation**:
- 단위 테스트: `useCanvasSync`의 변경 감지 로직 (lastModified 비교)
- 통합 테스트: 다른 탭에서 설명 수정 → 현재 탭에서 10초 이내 갱신 확인
- 성능 테스트: 폴링 간격이 서버 부하에 미치는 영향 (10초 간격은 안전)

**Complexity**: Medium
**Estimated files**: 신규 1, 수정 4

---

### G6: 시맨틱 검색 (벡터 기반)

**What**: 기존 `SchemaSearchBar`에 시맨틱 검색 모드를 추가. Synapse의 기존 `POST /api/v3/synapse/graph/vector-search` API를 활용하여 자연어 질의로 테이블/컬럼을 검색하고, 유사도 순으로 결과를 정렬.

**Where**:
- 신규: `canvas/src/shared/api/graphSearchApi.ts` -- Synapse graph vector-search API 클라이언트
- 수정: `canvas/src/features/nl2sql/components/SchemaSearchBar.tsx` -- 시맨틱/텍스트 모드 토글 추가
- 수정: `canvas/src/features/nl2sql/types/schema.ts` -- `SchemaSearchResult`에 `score` 필드 추가

**How**:

1) API 클라이언트 생성 (`graphSearchApi.ts`):

```typescript
// canvas/src/shared/api/graphSearchApi.ts
import { synapseApi } from '@/lib/api/clients';

export interface VectorSearchResult {
  type: 'table' | 'column' | 'query';
  name: string;
  score: number;
  context?: string;  // 매칭된 설명 텍스트
}

export async function vectorSearch(params: {
  query: string;
  target?: 'table' | 'column' | 'all';
  topK?: number;
}): Promise<VectorSearchResult[]> {
  const res = await synapseApi.post('/api/v3/synapse/graph/vector-search', {
    query: params.query,
    target: params.target ?? 'all',
    top_k: params.topK ?? 10,
  });
  const body = res as any;
  return body.data?.results ?? [];
}
```

2) `SchemaSearchBar.tsx` 수정:

- 검색바 우측에 텍스트/시맨틱 모드 토글 아이콘 버튼 추가
- 시맨틱 모드 활성 시:
  - 검색어 입력 후 300ms 디바운스 → `vectorSearch()` 호출
  - 결과를 `score` 내림차순 정렬
  - 각 결과 옆에 유사도 점수 뱃지 표시

```tsx
// SchemaSearchBar 내부에 추가
const [searchMode, setSearchMode] = useState<'text' | 'semantic'>('text');

// 시맨틱 모드일 때의 결과 조회
const vectorResults = useQuery({
  queryKey: ['vector-search', debouncedQuery],
  queryFn: () => vectorSearch({ query: debouncedQuery, target: 'all' }),
  enabled: searchMode === 'semantic' && debouncedQuery.length >= 2,
});
```

3) `SchemaSearchResult` 타입 확장:

```typescript
export interface SchemaSearchResult {
  // ... 기존 필드 ...
  score?: number;        // 시맨틱 유사도 점수 (0~1)
  searchMode?: 'text' | 'semantic';
}
```

**Dependencies**: 없음 (기존 벡터 검색 API 활용)

**Validation**:
- 단위 테스트: `vectorSearch()` API 클라이언트 호출 검증
- 통합 테스트: "매출 관련 테이블" 같은 자연어 검색 → 관련 테이블 결과 반환 확인
- UX 테스트: 텍스트/시맨틱 모드 전환 시 결과 목록 즉시 갱신

**Complexity**: Medium
**Estimated files**: 신규 1, 수정 2

---

### G8: 테이블 데이터 프리뷰 패널

**What**: 캔버스에서 테이블 클릭 시 실제 데이터 행 10개를 미리보는 슬라이드 패널. Oracle 서비스의 `POST /text2sql/ask` API를 활용하여 `SELECT * FROM {schema}.{table} LIMIT 10` 실행.

**Where**:
- 신규: `canvas/src/features/nl2sql/components/DataPreviewPanel.tsx` -- 데이터 프리뷰 슬라이드 패널
- 신규: `canvas/src/features/nl2sql/hooks/useDataPreview.ts` -- 데이터 프리뷰 조회 훅
- 수정: `canvas/src/features/nl2sql/components/SchemaCanvas.tsx` -- 테이블 클릭 시 프리뷰 패널 열기

**How**:

1) 데이터 프리뷰 훅 (`useDataPreview.ts`):

```typescript
// canvas/src/features/nl2sql/hooks/useDataPreview.ts
import { useQuery } from '@tanstack/react-query';
import { oracleApi } from '@/lib/api/clients';

interface PreviewData {
  columns: string[];
  rows: unknown[][];
  rowCount: number;
}

async function fetchPreview(
  datasourceId: string,
  schemaName: string,
  tableName: string,
): Promise<PreviewData> {
  // Oracle text2sql/ask API를 활용하여 SELECT 실행
  const res = await oracleApi.post('/api/v1/oracle/text2sql/ask', {
    question: `SELECT * FROM ${schemaName}.${tableName} LIMIT 10`,
    datasource_id: datasourceId,
    mode: 'direct',  // 직접 SQL 실행 모드
  });
  const body = res as any;
  return {
    columns: body.data?.columns ?? [],
    rows: body.data?.rows ?? [],
    rowCount: body.data?.row_count ?? 0,
  };
}

export function useDataPreview(params: {
  datasourceId: string;
  schemaName: string;
  tableName: string;
  enabled: boolean;
}) {
  return useQuery({
    queryKey: ['data-preview', params.datasourceId, params.schemaName, params.tableName],
    queryFn: () => fetchPreview(params.datasourceId, params.schemaName, params.tableName),
    enabled: params.enabled && !!params.datasourceId && !!params.tableName,
    staleTime: 30_000,  // 30초 캐시
  });
}
```

2) `DataPreviewPanel.tsx` -- 슬라이드 패널 컴포넌트:

```typescript
// canvas/src/features/nl2sql/components/DataPreviewPanel.tsx
interface DataPreviewPanelProps {
  tableName: string;
  schemaName: string;
  datasourceId: string;
  open: boolean;
  onClose: () => void;
}
```

UI 구성:
- shadcn/ui `Sheet` (슬라이드 패널) 또는 커스텀 패널
- 상단: 테이블명 + 닫기 버튼
- 중앙: TanStack Table 기반 데이터 그리드 (10행)
- 하단: 행 수 표시 + "전체 쿼리 실행" 버튼 (NL2SQL 채팅으로 연결)
- 로딩 상태: Skeleton UI
- 에러 상태: 연결 실패 메시지

3) `SchemaCanvas.tsx` 수정:
- `TableChip` 클릭 이벤트에 프리뷰 패널 열기 추가
- `DataPreviewPanel` 컴포넌트 하단에 렌더링

**Dependencies**: 없음 (Oracle API 활용)

**Validation**:
- 단위 테스트: `useDataPreview` 훅의 API 호출 + 에러 핸들링
- 통합 테스트: 실제 데이터소스 연결 후 테이블 클릭 → 데이터 10행 표시 확인
- 엣지 케이스: 데이터소스 미연결 시 적절한 에러 메시지, 빈 테이블(0행) 처리

**Complexity**: Medium
**Estimated files**: 신규 2, 수정 1

---

## 5. 파일 변경 목록

### 5.1 신규 파일

| 파일 경로 | Gap | 목적 |
|-----------|-----|------|
| `canvas/src/shared/api/schemaEditApi.ts` | G3 | Synapse schema-edit API 클라이언트 |
| `canvas/src/shared/api/graphSearchApi.ts` | G6 | Synapse graph vector-search API 클라이언트 |
| `canvas/src/features/nl2sql/hooks/useSchemaEdit.ts` | G3 | TanStack Query 기반 스키마 편집 훅 |
| `canvas/src/features/nl2sql/hooks/useFkVisibility.ts` | G1 | FK 소스별 가시성 상태 훅 |
| `canvas/src/features/nl2sql/hooks/useDisplayMode.ts` | G7 | 논리명/물리명 표시 모드 훅 |
| `canvas/src/features/nl2sql/hooks/useCanvasSync.ts` | G5 | 폴링 기반 캔버스 동기화 훅 |
| `canvas/src/features/nl2sql/hooks/useDataPreview.ts` | G8 | 테이블 데이터 프리뷰 훅 |
| `canvas/src/features/nl2sql/components/FkVisibilityToolbar.tsx` | G1 | FK 소스별 토글 버튼 UI |
| `canvas/src/features/nl2sql/components/CardinalityModal.tsx` | G2 | 관계 편집 모달 다이얼로그 |
| `canvas/src/features/nl2sql/components/DataPreviewPanel.tsx` | G8 | 데이터 프리뷰 슬라이드 패널 |

### 5.2 수정 파일

| 파일 경로 | Gap | 변경 내용 |
|-----------|-----|-----------|
| `services/synapse/app/services/related_tables_service.py` | G4 | `ColumnPair` 모델 추가, `_row_to_item()`에서 pairs 생성 |
| `services/synapse/app/api/schema_edit.py` | G5 | `GET /last-modified` 엔드포인트 추가 |
| `services/synapse/app/services/schema_edit_service.py` | G5 | `get_last_modified()` 메서드 추가 |
| `canvas/src/shared/types/schemaNavigation.ts` | G4 | `ColumnPair` 인터페이스, `RelatedTableItem.columnPairs` 추가 |
| `canvas/src/features/nl2sql/types/schema.ts` | G1,G4,G6 | `FkSource` 타입, `SchemaRelationship.source/columnPairs`, `SchemaSearchResult.score` 추가 |
| `canvas/src/features/datasource/utils/mermaidCodeGen.ts` | G1,G4,G7 | 소스별 관계선 스타일, column_pairs 기반 렌더링, displayMode 파라미터 |
| `canvas/src/features/nl2sql/components/SchemaCanvas.tsx` | G1,G2,G5,G7,G8 | 가시성 툴바, 모달 상태, sync 훅, 표시 모드, 프리뷰 패널 통합 |
| `canvas/src/features/nl2sql/components/RelationshipManager.tsx` | G2,G3 | API 연동, CardinalityModal 열기로 변경 |
| `canvas/src/features/nl2sql/components/SchemaSearchBar.tsx` | G6 | 시맨틱/텍스트 모드 토글, 벡터 검색 통합 |
| `canvas/src/features/nl2sql/components/TableDetailPanel.tsx` | G3 | 인라인 설명 편집 UI |
| `canvas/src/features/nl2sql/components/ColumnDetailPanel.tsx` | G3 | 컬럼 설명 인라인 편집 UI |
| `canvas/src/shared/api/schemaEditApi.ts` | G5 | `getLastModified()` 함수 추가 |

---

## 6. 테스트 전략

### 6.1 단위 테스트

| 테스트 파일 | 대상 | 핵심 시나리오 |
|------------|------|-------------|
| `services/synapse/tests/unit/test_column_pairs.py` | G4 | `_row_to_item()`에서 column_pairs 생성, 빈 배열/불균등 배열 처리 |
| `services/synapse/tests/unit/test_schema_edit_service.py` | G3,G5 | `get_last_modified()`, 관계 CRUD 서비스 로직 |
| `canvas/src/features/nl2sql/hooks/useFkVisibility.test.ts` | G1 | 토글 상태 전환, isVisible 판정 |
| `canvas/src/features/nl2sql/hooks/useSchemaEdit.test.ts` | G3 | mutation 호출, 캐시 무효화 |
| `canvas/src/features/nl2sql/hooks/useDisplayMode.test.ts` | G7 | 모드 토글, 초기값 |
| `canvas/src/features/nl2sql/hooks/useCanvasSync.test.ts` | G5 | 타임스탬프 비교, 콜백 호출 |
| `canvas/src/features/nl2sql/hooks/useDataPreview.test.ts` | G8 | API 호출, enabled 조건, 에러 처리 |
| `canvas/src/features/nl2sql/components/CardinalityModal.test.tsx` | G2 | 폼 유효성, 저장/취소, column_pairs UI |
| `canvas/src/features/nl2sql/components/DataPreviewPanel.test.tsx` | G8 | 로딩/에러 상태, 데이터 그리드 렌더링 |

### 6.2 통합 테스트

| 테스트 시나리오 | 관련 Gap | 검증 내용 |
|----------------|---------|-----------|
| 관계 추가 E2E 플로우 | G2,G3,G4 | 모달에서 관계 추가 → API 호출 → 목록 갱신 → ERD 반영 |
| FK 가시성 토글 | G1,G4 | DDL off → 해당 관계선 비표시, 재활성 → 다시 표시 |
| 시맨틱 검색 → 테이블 추가 | G6 | 자연어 검색 → 결과 클릭 → 캔버스에 테이블 추가 |
| 테이블 프리뷰 | G8 | 테이블 클릭 → 프리뷰 패널 → 데이터 10행 표시 |
| 실시간 갱신 | G5 | 설명 수정 → 10초 이내 캔버스 갱신 |

### 6.3 엣지 케이스

- column_pairs 빈 배열 (FK 관계 있지만 컬럼 매핑 정보 없음) -- 폴백 처리
- description 없는 테이블의 논리명 모드 -- 물리명 폴백
- 데이터소스 미연결 상태에서 프리뷰 시도 -- 적절한 에러 메시지
- 동일 테이블 쌍의 복수 FK (예: orders.billing_address_id, orders.shipping_address_id 모두 addresses 참조) -- column_pairs로 구분
- 허브 테이블(FK 10개 이상)의 가시성 토글 -- 성능 영향 최소화

---

## 7. 위험 평가

| 위험 | 영향도 | 발생 확률 | 완화 전략 |
|------|--------|----------|-----------|
| Mermaid.js의 관계선 스타일 커스터마이징 한계 | 중 | 중 | Mermaid CSS 클래스 오버라이드로 해결. 불가 시 SVG 후처리 적용 |
| 폴링 기반 실시간 업데이트의 서버 부하 | 저 | 저 | 10초 간격 + 가벼운 타임스탬프 비교 쿼리. 사용자 수 증가 시 SSE 전환 계획 |
| Oracle text2sql/ask API의 직접 SQL 실행 보안 | 고 | 저 | SELECT만 허용하는 SQL Guard AST 검증이 이미 Oracle에 구현됨 (`sql_guard_ast.py`). 추가로 LIMIT 강제 적용 |
| Neo4j FK_TO 관계에 source 속성 미존재 | 중 | 고 | 현재 Neo4j FK_TO 관계에는 source 프로퍼티가 없음. 사용자 추가 관계는 PostgreSQL `schema_relationships` 테이블에 저장되므로, `source='user'`는 PostgreSQL 조회로 판별. DDL/Fabric 구분은 metadata_graph에서 추론 |
| `SchemaCanvas.tsx` 수정 범위 확대 | 중 | 중 | 각 Gap의 로직을 독립 훅/컴포넌트로 분리하여 SchemaCanvas는 조합 역할만 유지. 파일 크기 250줄 이내 목표 |
| Mermaid ERD에서 복수 column_pairs 관계선 렌더링 | 중 | 중 | Mermaid는 동일 테이블 쌍 간 하나의 관계선만 지원. 복수 pairs는 라벨에 "col1,col2" 형태로 표시 |

---

## 8. 구현 일정 (Phase별)

### Phase 1: 기반 인프라 (G4 + G3) -- 예상 3일

| 작업 | 담당 영역 | 병렬 가능 | 예상 일수 |
|------|----------|-----------|----------|
| G4-1: `ColumnPair` Pydantic 모델 + `_row_to_item` 수정 | Backend | Yes | 0.5 |
| G4-2: 프론트엔드 타입 동기화 (`ColumnPair` 인터페이스) | Frontend | Yes | 0.5 |
| G4-3: `mermaidCodeGen.ts` column_pairs 기반 렌더링 | Frontend | G4-2 후 | 1 |
| G3-1: `schemaEditApi.ts` API 클라이언트 | Frontend | Yes | 0.5 |
| G3-2: `useSchemaEdit.ts` TanStack Query 훅 | Frontend | G3-1 후 | 0.5 |
| G3-3: 인라인 편집 UI (TableDetailPanel, ColumnDetailPanel) | Frontend | G3-2 후 | 1 |
| 단위 테스트 | Both | G4/G3 완료 후 | 0.5 |

### Phase 2: 핵심 UX (G1 + G2) -- 예상 3일

| 작업 | 담당 영역 | 병렬 가능 | 예상 일수 |
|------|----------|-----------|----------|
| G1-1: `useFkVisibility` 훅 + `FkVisibilityToolbar` | Frontend | Yes | 1 |
| G1-2: `mermaidCodeGen.ts` 소스별 스타일 분기 | Frontend | G1-1 후 | 0.5 |
| G1-3: `SchemaCanvas.tsx` 가시성 툴바 통합 | Frontend | G1-2 후 | 0.5 |
| G2-1: `CardinalityModal.tsx` 컴포넌트 | Frontend | Yes | 1.5 |
| G2-2: `RelationshipManager.tsx` 모달 연동 | Frontend | G2-1 후 | 0.5 |
| 단위/통합 테스트 | Frontend | G1/G2 완료 후 | 0.5 |

### Phase 3: 개선 (G7 + G5) -- 예상 2.5일

| 작업 | 담당 영역 | 병렬 가능 | 예상 일수 |
|------|----------|-----------|----------|
| G7-1: `useDisplayMode` 훅 + 토글 UI | Frontend | Yes | 0.5 |
| G7-2: `mermaidCodeGen.ts` displayMode 분기 | Frontend | G7-1 후 | 0.5 |
| G5-1: 백엔드 `GET /last-modified` 엔드포인트 | Backend | Yes | 0.5 |
| G5-2: `useCanvasSync` 훅 | Frontend | G5-1 후 | 0.5 |
| G5-3: `SchemaCanvas.tsx` 통합 | Frontend | G5-2 후 | 0.5 |
| 단위/통합 테스트 | Both | 완료 후 | 0.5 |

### Phase 4: 부가 기능 (G6 + G8) -- 예상 2.5일

| 작업 | 담당 영역 | 병렬 가능 | 예상 일수 |
|------|----------|-----------|----------|
| G6-1: `graphSearchApi.ts` API 클라이언트 | Frontend | Yes | 0.5 |
| G6-2: `SchemaSearchBar.tsx` 시맨틱 모드 통합 | Frontend | G6-1 후 | 1 |
| G8-1: `useDataPreview` 훅 | Frontend | Yes | 0.5 |
| G8-2: `DataPreviewPanel.tsx` 컴포넌트 | Frontend | G8-1 후 | 1 |
| G8-3: `SchemaCanvas.tsx` 프리뷰 연동 | Frontend | G8-2 후 | 0.5 |
| 단위/통합 테스트 | Frontend | 완료 후 | 0.5 |

### 전체 일정 요약

| Phase | 기간 | 핵심 산출물 |
|-------|------|-----------|
| Phase 1 | 3일 | column_pairs 구조, 스키마 편집 API 연동 |
| Phase 2 | 3일 | FK 가시성 토글, 관계 편집 모달 |
| Phase 3 | 2.5일 | 논리명 토글, 실시간 캔버스 갱신 |
| Phase 4 | 2.5일 | 시맨틱 검색, 데이터 프리뷰 |
| **합계** | **~11일** | G1-G8 전체 구현 완료 |
