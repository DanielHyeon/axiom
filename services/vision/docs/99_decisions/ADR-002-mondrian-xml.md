# ADR-002: Mondrian XML 기반 큐브 정의

## 상태

Accepted

## 배경

OLAP 피벗 분석 엔진에서 큐브(차원, 측도, 조인)를 정의하는 형식을 선택해야 한다. K-AIR의 data-platform-olap-main에서 이미 Mondrian XML 형식을 사용하고 있으며, 이를 Axiom Vision에 이식하는 것이 기본 방향이다.

### 요구사항

- 큐브의 차원, 계층, 측도, 조인을 명확하게 정의
- 파서(xml_parser.py)가 이미 존재하며 이식 가능
- 비개발자(데이터 분석가)도 이해할 수 있는 형식
- 버전 관리(Git) 가능
- 프로그래밍 언어 독립적

## 고려한 옵션

### 1. Mondrian XML

- **장점**: K-AIR에서 파서 이미 구현(80%), OLAP 업계 표준 형식, 풍부한 레퍼런스, XML은 스키마 검증 가능(XSD)
- **단점**: XML 자체의 장황함, 작은 변경에도 파일이 큼

### 2. YAML 기반 커스텀 형식

- **장점**: 가독성 높음, 간결, Python 파싱 쉬움
- **단점**: 커스텀 형식이므로 표준 도구 활용 불가, 파서를 처음부터 작성해야 함, OLAP 도구와 호환 불가

### 3. JSON Schema

- **장점**: API와 일관된 형식, JavaScript/Python 모두 쉽게 파싱
- **단점**: 계층 구조 표현이 XML보다 불편, OLAP 표준이 아님

### 4. Python DSL (코드로 정의)

- **장점**: 타입 체크 가능, IDE 지원
- **단점**: 비개발자 접근 불가, 버전 관리 시 diff가 불명확

## 선택한 결정

**Mondrian XML 형식**

## 근거

1. **이식 비용 최소화**: K-AIR의 xml_parser.py를 거의 그대로 이식 가능. 파서 로직이 이미 검증됨.

2. **OLAP 업계 표준**: Mondrian, Apache Kylin 등 OLAP 도구에서 사용하는 표준 형식. 향후 다른 OLAP 도구와 연동 시 호환성 확보.

3. **스키마 검증**: XSD로 XML 유효성 검증 가능. 잘못된 큐브 정의를 업로드 시점에 차단.

4. **분리 가능한 설정**: 큐브 정의가 코드와 분리되어, 데이터 분석가가 큐브를 추가/수정할 수 있음.

5. **Git 친화적**: 텍스트 파일이므로 변경 이력 추적 가능.

## 결과

### 긍정적 영향

- K-AIR 이식 시간 단축 (파서 80% 재사용)
- OLAP 전문가가 큐브를 직접 정의/수정 가능
- 큐브 정의와 엔진 코드 분리로 독립적 변경 가능

### 부정적 영향

- XML의 장황함 (YAML 대비 약 2배 길이)
- XML 편집기 필요 (IDE XML 플러그인)

## 재평가 조건

- 큐브 정의를 UI에서 동적으로 생성해야 할 때 (JSON 형식이 더 적합할 수 있음)
- OLAP 도구를 Mondrian이 아닌 다른 엔진으로 교체할 때
- 큐브 수가 100개 이상으로 증가하여 XML 관리가 어려워질 때

---

## 증거

- K-AIR data-platform-olap-main/xml_parser.py (원본 파서)
- 01_architecture/olap-engine.md Section 2
- 03_backend/mondrian-parser.md (이식 상세)
