# ADR-001: Vue 3 에서 React 18로의 전환

## 상태

Accepted (수락됨)

## 배경

K-AIR 프로젝트는 4개의 Vue 3 기반 프론트엔드 애플리케이션으로 구성되어 있었다.

- `process-gpt-vue3-main` (Vue 3.2 + Vuetify 3.4)
- `robo-data-fabric/frontend` (Vue 3.5 + Headless UI)
- `data-platform-olap/frontend` (Vue 3.5 + Tailwind)
- `eventstorming-tool` (Vue 3.5 + Konva.js)

Axiom Canvas는 이 4개를 **하나의 통합 웹 애플리케이션**으로 재작성해야 했다. 이 시점에서 Vue 3를 유지할 것인지, React 18로 전환할 것인지 결정이 필요했다.

### 결정이 필요했던 이유

1. 4개 앱의 Vue 버전 불일치 (3.2 vs 3.5)
2. UI 라이브러리 3종 혼재 (Vuetify, Headless UI, 순수 Tailwind)
3. 향후 팀 확장 시 채용 풀 고려
4. 생태계 라이브러리 풍부성 (특히 그래프 시각화, OLAP UI)
5. TypeScript 통합 성숙도

## 고려한 옵션

### 옵션 1: Vue 3 유지 + 통합

- 기존 코드 재사용 가능성 높음
- 학습 비용 없음
- Pinia + Vue Router 유지
- UI 라이브러리를 하나로 통일 필요 (Vuetify 또는 Headless UI)

### 옵션 2: React 18로 전환

- 전체 재작성 필요
- 더 큰 생태계 (react-force-graph, @dnd-kit, TanStack 시리즈)
- TypeScript와의 더 깊은 통합 (JSX/TSX)
- 한국 시장 채용 풀 우위

### 옵션 3: Next.js (React SSR)

- SSR/SSG 이점
- 프론트엔드 서버 운영 필요
- Canvas는 인증 필수 SPA -> SSR 이점 제한적

## 선택한 결정

**옵션 2: React 18로 전환**

## 근거

| 기준 | Vue 3 유지 | React 18 전환 | 비중 |
|------|-----------|--------------|------|
| **생태계 라이브러리** | 제한적 (force-graph, OLAP 관련) | 풍부함 | 30% |
| **TypeScript 통합** | template에서 제한적 | JSX에서 완전한 타입 추론 | 20% |
| **채용 풀** | 한국 시장 중소 | 한국 시장 우세 | 20% |
| **TanStack 시리즈 호환** | @tanstack/vue-query 존재하나 React만큼 성숙하지 않음 | 네이티브 지원 | 15% |
| **기존 코드 재사용** | 높음 (70%+ 재사용) | 낮음 (로직만 참조) | 15% |

### 핵심 결정 요인

1. **react-force-graph**: 온톨로지 브라우저에 필수. Vue 대응 라이브러리가 Mermaid(정적)밖에 없음
2. **@dnd-kit**: OLAP 피벗 DnD에 필수. vue-draggable은 접근성 지원 부족
3. **TanStack Query + Table**: React 버전이 Vue 버전보다 기능/문서 모두 우세
4. **Shadcn/ui**: ADR-002에서 선정, React 전용

## 부정적 결과

- K-AIR 코드 직접 재사용 불가 (전체 재작성)
- Vue 경험 개발자의 학습 곡선
- 전환 기간 동안 K-AIR와 Canvas 병렬 운영 필요

## 긍정적 결과

- 4개 앱의 기술 부채 한 번에 청산
- Composition API -> Custom Hooks 매핑이 1:1에 가까워 로직 이식 용이
- 통합 디자인 시스템(Shadcn/ui) 적용 가능

## 재평가 조건

- 이 결정은 **프로젝트 초기**에 내린 것이므로 재평가 가능성은 낮다
- 다만, React 생태계에 큰 파편화가 발생하거나, Vue 생태계가 Canvas 요구를 완전히 충족하는 경우 재검토

---

## 변경 이력

| 날짜 | 작성자 | 내용 |
|------|--------|------|
| 2026-02-19 | Axiom Team | 초기 작성 |
