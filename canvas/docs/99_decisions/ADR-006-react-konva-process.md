# ADR-006: 비즈니스 프로세스 디자이너 캔버스에 react-konva 사용

## 상태

Accepted (수락됨)

## 배경

Axiom Canvas에 8번째 기능 영역으로 **비즈니스 프로세스 디자이너**를 추가한다. 이 기능은 K-AIR의 `eventstorming-tool-vite-main` 프로젝트를 비즈니스 프로세스 수준으로 확장/재구축한 것이다.

K-AIR eventstorming-tool은 **Vue 3 + vue-konva + Yjs**로 구현되어 있으며, 다음과 같은 특성을 가진다:

- 스티키 노트(Sticky Note) 방식의 자유 배치 캔버스
- 7종 EventStorming 노드 (ContextBox, Command, Event, Aggregate, Policy, Actor, ReadModel)
- Konva.js 기반 2D 캔버스 렌더링 (Rect, Text, Arrow, Group 등)
- Yjs CRDT 기반 실시간 다중 사용자 협업
- 드래그앤드롭, 줌, 패닝 인터랙션

Canvas는 React 18 기반이므로(ADR-001), vue-konva를 직접 사용할 수 없다. 비즈니스 프로세스 디자이너의 캔버스 렌더링 라이브러리를 선택해야 했다.

### 결정이 필요했던 이유

1. vue-konva 코드를 React 환경으로 이식해야 함
2. EventStorming의 스티키 노트 UX(자유 배치, 색상 구분, 리사이즈)를 보존해야 함
3. Yjs 실시간 협업과의 통합이 필수적임
4. 프로세스 마이닝 결과 오버레이(병목 하이라이트, 이탈 경로 점선)를 캔버스 위에 렌더링해야 함
5. 노드 100개 이상의 프로세스 모델에서도 성능이 유지되어야 함

## 고려한 옵션

### 옵션 1: react-konva

- Konva.js의 공식 React 래퍼
- vue-konva와 동일한 Konva.js 엔진 사용
- React 선언적 패턴 (JSX로 Konva 객체 선언)
- npm 주간 다운로드 약 200K, 활발한 유지보수

### 옵션 2: React Flow (reactflow.dev)

- 노드 기반 다이어그램 전문 라이브러리
- 노드/엣지 그래프에 특화
- 자체 레이아웃 엔진 포함
- 스티키 노트 UX보다 다이어그램 UX에 최적화

### 옵션 3: D3.js (직접 SVG)

- SVG 기반, 완전한 저수준 제어
- React와의 통합이 복잡 (DOM 직접 조작 vs React 가상 DOM 충돌)
- 가장 높은 자유도, 가장 높은 구현 비용

### 옵션 4: 커스텀 SVG (React 네이티브)

- React 컴포넌트로 SVG 직접 구현
- 외부 의존성 없음
- 줌/패닝/히트 테스트를 모두 직접 구현해야 함

## 선택한 결정

**옵션 1: react-konva**

## 근거

| 기준 | react-konva | React Flow | D3.js | 커스텀 SVG | 비중 |
|------|-----------|------------|-------|-----------|------|
| **K-AIR 이식 용이성** | 매우 높음 (동일 Konva.js) | 낮음 (패러다임 다름) | 낮음 (완전 재작성) | 중간 | 35% |
| **스티키 노트 UX 보존** | 완벽 (동일 렌더링 엔진) | 제한적 (그래프 UX 중심) | 가능 (고비용) | 가능 (고비용) | 25% |
| **캔버스 성능 (100+ 노드)** | 우수 (Canvas 2D) | 양호 (HTML DOM) | 양호 (SVG) | 양호 (SVG) | 15% |
| **Yjs 통합 난이도** | 낮음 (기존 패턴 재사용) | 중간 | 높음 | 중간 | 15% |
| **학습 곡선** | 낮음 (Konva.js 지식 재활용) | 중간 | 높음 | 해당없음 | 10% |

### 핵심 결정 요인

1. **동일 Konva.js 엔진**: vue-konva와 react-konva는 동일한 Konva.js 위에 구축된다. 렌더링 결과가 픽셀 단위로 동일하므로, K-AIR의 스티키 노트 UX를 그대로 보존할 수 있다.

2. **이식 비용 최소화**: vue-konva의 `<v-rect>`, `<v-text>`, `<v-arrow>` 등은 react-konva의 `<Rect>`, `<Text>`, `<Arrow>`와 1:1로 대응된다. 템플릿 -> JSX 변환만 하면 캔버스 렌더링 로직의 약 70%를 재활용할 수 있다.

3. **Yjs 통합 검증 완료**: K-AIR에서 Konva.js + Yjs 조합이 이미 검증되었다. Yjs는 프레임워크 무관하므로, React 환경에서도 동일한 동기화 로직을 사용할 수 있다.

4. **React Flow 부적합 사유**: React Flow는 노드 기반 다이어그램(워크플로우, 파이프라인)에 적합하지만, EventStorming의 **자유 배치 스티키 노트** UX와는 패러다임이 다르다. ContextBox(영역 그룹), 자유 위치 배치, 노드 리사이즈 등이 React Flow의 그리드 기반 레이아웃과 충돌한다.

## 부정적 결과

- react-konva는 HTML Canvas 2D 기반이므로 **접근성(a11y)**이 제한적이다. 스크린 리더 지원을 위해 별도의 시맨틱 HTML 레이어가 필요할 수 있다.
- Konva.js의 이벤트 시스템은 React 이벤트 시스템과 별도이므로, 이벤트 버블링이나 합성 이벤트를 기대하면 안 된다.
- Canvas 2D 기반이므로 텍스트 선택/복사, 브라우저 검색(Ctrl+F)이 불가능하다. 속성 패널은 일반 React 컴포넌트로 구현하여 이 제약을 보완한다.

## 긍정적 결과

- K-AIR eventstorming-tool의 Konva.js 지식을 팀 내에서 그대로 활용할 수 있다.
- vue-konva -> react-konva 전환 학습 비용이 매우 낮다 (래퍼 API만 학습).
- Canvas 2D 기반이므로 대량 노드(100+)에서 DOM 기반 대비 우수한 렌더링 성능을 보인다.
- 프로세스 마이닝 오버레이(병목 하이라이트, 이탈 경로)를 동일 Canvas 위에 자연스럽게 렌더링할 수 있다.

## 재평가 조건

- react-konva의 유지보수가 중단될 경우 (현재 활발하나 핵심 관리자 1명)
- React 19+ 에서 react-konva 호환성 문제가 발생할 경우
- 접근성 요구사항이 엄격해져서 Canvas 2D 기반으로는 충족이 불가능할 경우
- 노드가 500개 이상으로 증가하여 WebGL 기반 렌더링(pixi.js 등)이 필요할 경우

---

## 근거 문서

- ADR-001: Vue 3에서 React 18로의 전환
- 01_architecture/component-architecture.md: ProcessDesigner 컴포넌트 트리
- 04_frontend/process-designer.md: 비즈니스 프로세스 디자이너 상세 설계

---

## 변경 이력

| 날짜 | 작성자 | 내용 |
|------|--------|------|
| 2026-02-20 | Axiom Team | 초기 작성 |
