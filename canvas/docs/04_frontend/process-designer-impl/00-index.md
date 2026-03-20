# Process Designer 구현 계획서

> 작성일: 2026-02-27
> 근거: `process-designer.md` (설계 v1.2) + `process-designer-gap-analysis.md`
> 참조 구현: K-AIR `eventstorming-tool-vite-main` (Vue 3 + vue-konva + Yjs)

---

## 문서 구조

| 문서 | 페이즈 | 핵심 목표 | 예상 기간 |
|------|:------:|-----------|:---------:|
| [01-foundation.md](./01-foundation.md) | Phase 1 | 타입 시스템 + 스토어 리팩터링 + 11종 노드 | 3-4일 |
| [02-canvas-core.md](./02-canvas-core.md) | Phase 2 | 연결선 4종 + 키보드 단축키 + 줌/패닝 | 3-4일 |
| [03-property-panel-ux.md](./03-property-panel-ux.md) | Phase 3 | 속성 패널 완성 + UX 상태(에러/빈/로딩) | 2-3일 |
| [04-yjs-collaboration.md](./04-yjs-collaboration.md) | Phase 4 | Yjs CRDT 도입 + 커서 공유 + 오프라인 | 4-5일 |
| [05-mining-ai.md](./05-mining-ai.md) | Phase 5 | 프로세스 마이닝 오버레이 + AI 역공학 | 4-5일 |
| [06-a11y-rbac.md](./06-a11y-rbac.md) | Phase 6 | 접근성(WCAG 2.1 AA) + RBAC | 2-3일 |

**총 예상: 18-24일 (1 FE 개발자 기준)**

---

## 페이즈 간 의존성

```
Phase 1 ──→ Phase 2 ──→ Phase 3
  │                        │
  └────→ Phase 4 ──────────┘
              │
              ▼
         Phase 5
              │
              ▼
         Phase 6
```

- Phase 1은 모든 후속 페이즈의 필수 선행 조건
- Phase 2, 3은 Phase 1 이후 병렬 작업 가능
- Phase 4(Yjs)는 Phase 1 직후 시작 가능하나, Phase 3의 UX 상태와 통합 필요
- Phase 5는 Phase 4(Yjs 데이터 계층) 완료 후
- Phase 6은 모든 기능 구현 후 최종 단계

---

## 파일 구조 목표

Phase 1 완료 후의 목표 디렉토리 구조:

```
features/process-designer/
├── api/
│   └── processDesignerApi.ts        # 캔버스 보드 CRUD API
├── components/
│   ├── canvas/
│   │   ├── ProcessCanvas.tsx         # react-konva Stage 래퍼
│   │   ├── CanvasNode.tsx            # 개별 노드 (Group+Rect+Text)
│   │   ├── ContextBoxNode.tsx        # Business Domain 영역 노드
│   │   ├── ConnectionLine.tsx        # 연결선 (Arrow)
│   │   ├── ConnectionPoint.tsx       # 노드 hover 시 연결 포인트
│   │   ├── SelectionRect.tsx         # 드래그 선택 영역
│   │   └── CollaboratorCursors.tsx   # Phase 4: 협업 커서
│   ├── toolbox/
│   │   └── ProcessToolbox.tsx        # 좌측 노드 팔레트
│   ├── property-panel/
│   │   ├── ProcessPropertyPanel.tsx  # 우측 속성 패널 컨테이너
│   │   ├── BasicProperties.tsx       # 이름, 설명, 색상
│   │   ├── TemporalProperties.tsx    # 시간축 속성
│   │   ├── MeasureBinding.tsx        # KPI 연결
│   │   └── EventLogBinding.tsx       # 데이터 소스 바인딩
│   ├── mining/
│   │   ├── ConformanceOverlay.tsx    # Phase 5: 캔버스 오버레이
│   │   ├── VariantList.tsx           # Phase 5: 변형 목록
│   │   └── ConformanceScore.tsx      # Phase 5: 적합도 점수
│   └── Minimap.tsx
├── hooks/
│   ├── useCanvasKeyboard.ts          # 키보드 단축키
│   ├── useCanvasInteraction.ts       # 마우스 이벤트 (줌/패닝/선택)
│   ├── useConnectionDraw.ts          # 연결선 그리기 모드
│   ├── useYjsCollaboration.ts        # Phase 4: Yjs 동기화
│   └── useProcessMining.ts           # Phase 5: 마이닝 API
├── store/
│   └── useProcessDesignerStore.ts    # UI 상태 (선택, 도구 모드)
├── types/
│   └── processDesigner.ts            # 모든 타입 정의
└── utils/
    ├── nodeConfig.ts                 # 노드 색상/크기/단축키 매핑
    ├── edgePoints.ts                 # 연결선 좌표 계산
    └── yjs-helpers.ts                # Phase 4: JS↔Yjs 변환
```

---

## 전역 통과 기준 (Global Acceptance Criteria)

모든 페이즈에 공통 적용:

| # | 기준 | 검증 방법 |
|:-:|------|-----------|
| G1 | TypeScript strict 모드 빌드 에러 0건 | `tsc --noEmit` |
| G2 | ESLint 경고/에러 0건 | `eslint --max-warnings 0` |
| G3 | 기존 테스트 회귀 없음 | `vitest run` |
| G4 | 콘솔 에러 없이 페이지 렌더링 | 브라우저 DevTools |
| G5 | 설계 문서 Forbidden 규칙 위반 없음 | 코드 리뷰 |
| G6 | K-AIR 기존 패턴과의 일관성 | 코드 리뷰 |

---

## K-AIR 참조 매핑

| K-AIR 파일 | 역할 | Canvas 대응 파일 |
|-----------|------|-----------------|
| `store.ts` | Yjs + 상태 관리 | `hooks/useYjsCollaboration.ts` + `store/useProcessDesignerStore.ts` |
| `types.ts` | CanvasItem, Connection 타입 | `types/processDesigner.ts` |
| `EventCanvas.vue` | 캔버스 + 툴박스 + 이벤트 | `components/canvas/ProcessCanvas.tsx` + `components/toolbox/ProcessToolbox.tsx` |
| `EventItem.vue` | 개별 노드 렌더링 | `components/canvas/CanvasNode.tsx` |
| `useCanvasLogic.ts` | 드래그/선택/키보드 로직 | `hooks/useCanvasInteraction.ts` + `hooks/useCanvasKeyboard.ts` |
| `PropertiesPanel.vue` | 우측 속성 편집 | `components/property-panel/ProcessPropertyPanel.tsx` |
| `ObjectProperties.vue` | 노드 위 속성 표시 | `components/canvas/CanvasNode.tsx` 내부 |
| `server.js` (Yjs WS) | WebSocket 서버 | 별도 백엔드 서비스 필요 |
