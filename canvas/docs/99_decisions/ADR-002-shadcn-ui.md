# ADR-002: Shadcn/ui 디자인 시스템 선택

## 상태

Accepted (수락됨)

## 배경

ADR-001에서 React 18 전환이 결정된 후, UI 컴포넌트 라이브러리를 선택해야 했다. K-AIR에서 Vuetify, Headless UI, 순수 Tailwind가 혼재되어 일관성 없는 UX가 문제였으므로, Canvas에서는 단일 디자인 시스템이 필수적이었다.

### 요구사항

1. 한글 친화적 타이포그래피
2. 다크 모드 완전 지원
3. 접근성(a11y) 기본 제공
4. 커스터마이징 자유도 (비즈니스 도메인 특화 UI 필요)
5. Tailwind CSS 호환
6. 번들 크기 최소화 (트리 셰이킹)

## 고려한 옵션

### 옵션 1: Ant Design (antd)

- 완성도 높은 컴포넌트 (Table, Form, DatePicker 등)
- 중국계 -> 한글 지원 양호
- 번들 크기 큼 (트리 셰이킹 제한적)
- 커스터마이징: CSS-in-JS 기반, Tailwind와 충돌

### 옵션 2: Material UI (MUI)

- Google Material Design 기반
- K-AIR Vuetify의 React 대응
- 번들 크기 큼
- 커스터마이징: emotion 기반, Tailwind와 충돌

### 옵션 3: Shadcn/ui + Tailwind CSS

- Radix UI primitives 기반 (접근성 기본)
- 소유 가능한(copy-paste) 컴포넌트
- Tailwind CSS 네이티브
- 번들 크기 최소 (사용하는 컴포넌트만 포함)
- 커스터마이징: 소스 코드 직접 수정 가능

### 옵션 4: Headless UI + 자체 스타일

- Tailwind Labs 공식 헤드리스 컴포넌트
- 스타일 완전 자유
- 컴포넌트 수 제한적 (Dialog, Popover 등만)
- 테이블, 폼 등은 직접 구현 필요

## 선택한 결정

**옵션 3: Shadcn/ui + Tailwind CSS**

## 근거

| 기준 | Ant Design | MUI | Shadcn/ui | Headless UI | 비중 |
|------|-----------|-----|-----------|------------|------|
| **커스터마이징** | 중간 | 중간 | 최고 | 최고 | 30% |
| **번들 크기** | 크다 | 크다 | 작다 | 최소 | 20% |
| **접근성** | 양호 | 양호 | 최고 (Radix) | 양호 | 15% |
| **Tailwind 호환** | 충돌 | 충돌 | 네이티브 | 네이티브 | 15% |
| **컴포넌트 완성도** | 최고 | 높음 | 높음 | 낮음 | 10% |
| **다크 모드** | 지원 | 지원 | CSS 변수 | 수동 | 10% |

### 핵심 결정 요인

1. **소유 가능한 컴포넌트**: Shadcn/ui는 node_modules가 아닌 프로젝트 내 복사. 비즈니스 도메인 특화 UI(상태 배지, 승인 워크플로우 등)를 자유롭게 수정 가능
2. **Tailwind CSS 네이티브**: 별도 CSS-in-JS 불필요, 빌드 파이프라인 단순
3. **CSS 변수 기반 테마**: 다크 모드를 CSS 변수 전환만으로 구현, JavaScript 오버헤드 없음
4. **Radix UI 기반 접근성**: Dialog, Select, Popover 등의 키보드 네비게이션, 스크린 리더 자동 지원

## 부정적 결과

- Ant Design/MUI 대비 "out of the box" 완성도 낮음 (DataTable, DatePicker 등은 추가 구현 필요)
- 컴포넌트 업데이트 시 수동 병합 필요 (npx shadcn-ui로 새 버전 확인)
- 디자이너가 Material/Ant 생태계 도구를 사용할 수 없음

## 긍정적 결과

- 번들 크기 대폭 감소 (antd 대비 1/5 추정)
- 도메인 특화 커스터마이징 자유도 확보
- Tailwind 단일 스타일링 체계

## 재평가 조건

- Shadcn/ui 프로젝트 유지보수 중단 시 (커뮤니티 포크 또는 자체 유지)
- 컴포넌트 요구사항이 Shadcn/ui 범위를 크게 초과할 때 (예: 복잡한 DateRangePicker, TreeView)

---

## 변경 이력

| 날짜 | 작성자 | 내용 |
|------|--------|------|
| 2026-02-19 | Axiom Team | 초기 작성 |
