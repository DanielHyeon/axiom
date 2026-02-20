# 엔진별 설정 파라미터 상세

<!-- affects: api, backend -->
<!-- requires-update: 02_api/datasource-api.md -->

## 이 문서가 답하는 질문

- 각 DB 엔진의 연결 파라미터는 무엇인가?
- 필수/선택 파라미터의 구분은?
- 기본값은 무엇인가?
- 엔진별 특이사항은?

---

## 1. PostgreSQL

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `host` | string | 필수 | - | 호스트 주소 |
| `port` | integer | 선택 | `5432` | 포트 번호 |
| `database` | string | 필수 | - | 데이터베이스 이름 |
| `user` | string | 필수 | - | 사용자 이름 |
| `password` | string | 필수 | - | 비밀번호 |
| `schema` | string | 선택 | `public` | 기본 스키마 |
| `sslmode` | string | 선택 | `prefer` | SSL 모드 (`disable`, `require`, `verify-ca`, `verify-full`) |

```json
{
  "host": "erp-db.internal",
  "port": 5432,
  "database": "enterprise_ops",
  "user": "reader",
  "password": "secure_password",
  "sslmode": "require"
}
```

**참고**: PostgreSQL에서 스키마 인트로스펙션 시 `information_schema`와 `pg_catalog` 뷰를 사용한다. 읽기 전용 권한(`SELECT` on `information_schema`)이 필요하다.

---

## 2. MySQL

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `host` | string | 필수 | - | 호스트 주소 |
| `port` | integer | 선택 | `3306` | 포트 번호 |
| `database` | string | 필수 | - | 데이터베이스 이름 |
| `user` | string | 필수 | - | 사용자 이름 |
| `password` | string | 필수 | - | 비밀번호 |
| `charset` | string | 선택 | `utf8mb4` | 문자셋 |
| `ssl` | boolean | 선택 | `false` | SSL 사용 여부 |

```json
{
  "host": "finance-db.internal",
  "port": 3306,
  "database": "accounting",
  "user": "readonly",
  "password": "secure_password",
  "charset": "utf8mb4"
}
```

**참고**: MySQL에서 schema = database이다. `information_schema.TABLES`, `information_schema.COLUMNS` 뷰 접근 권한 필요.

---

## 3. Oracle

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `host` | string | 필수 | - | 호스트 주소 |
| `port` | integer | 선택 | `1521` | 포트 번호 |
| `sid` | string | 조건부 | - | Oracle SID (service_name과 택 1) |
| `service_name` | string | 조건부 | - | Oracle Service Name (sid와 택 1) |
| `user` | string | 필수 | - | 사용자 이름 |
| `password` | string | 필수 | - | 비밀번호 |
| `encoding` | string | 선택 | `UTF-8` | 문자 인코딩 |

```json
{
  "host": "oracle-db.internal",
  "port": 1521,
  "service_name": "ENTERPRISE",
  "user": "APP_READER",
  "password": "secure_password"
}
```

**참고**: Oracle에서 schema = user이다. `ALL_TAB_COLUMNS`, `ALL_CONSTRAINTS`, `ALL_TAB_COMMENTS` 등 딕셔너리 뷰 접근 필요. `sid`와 `service_name` 중 하나는 반드시 제공해야 한다.

---

## 4. MongoDB

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `host` | string | 필수 | - | 호스트 주소 |
| `port` | integer | 선택 | `27017` | 포트 번호 |
| `database` | string | 필수 | - | 데이터베이스 이름 |
| `username` | string | 선택 | - | 사용자 이름 |
| `password` | string | 선택 | - | 비밀번호 |
| `auth_source` | string | 선택 | `admin` | 인증 소스 DB |

```json
{
  "host": "mongo.internal",
  "port": 27017,
  "database": "documents",
  "username": "reader",
  "password": "secure_password",
  "auth_source": "admin"
}
```

**주의**: MongoDB는 스키마 인트로스펙션을 **지원하지 않는다** (스키마리스 DB). 쿼리 실행만 가능하다.

---

## 5. Redis

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `host` | string | 필수 | - | 호스트 주소 |
| `port` | integer | 선택 | `6379` | 포트 번호 |
| `password` | string | 선택 | - | 비밀번호 |
| `db` | integer | 선택 | `0` | DB 번호 |

```json
{
  "host": "redis.internal",
  "port": 6379,
  "password": "secure_password",
  "db": 0
}
```

---

## 6. Elasticsearch

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `hosts` | string | 필수 | - | 호스트 URL (쉼표 구분 가능) |
| `username` | string | 선택 | - | 사용자 이름 |
| `password` | string | 선택 | - | 비밀번호 |
| `scheme` | string | 선택 | `https` | 프로토콜 |

```json
{
  "hosts": "https://es.internal:9200",
  "username": "elastic",
  "password": "secure_password"
}
```

---

## 7. Web

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `url` | string | 필수 | - | 웹 API URL |

```json
{
  "url": "https://api.dart.fss.or.kr/api"
}
```

**용도**: 외부 공시 시스템(DART 등) API 연동.

---

## 8. OpenAI (MindsDB ML 엔진)

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `api_key` | string | 필수 | - | OpenAI API 키 |
| `model` | string | 선택 | `gpt-4o` | 모델 이름 |
| `max_tokens` | integer | 선택 | `1000` | 최대 토큰 수 |

```json
{
  "api_key": "sk-...",
  "model": "gpt-4o"
}
```

**용도**: MindsDB 내에서 ML 예측 모델로 사용.

---

## 9. 관련 문서

| 문서 | 설명 |
|------|------|
| `02_api/datasource-api.md` | 데이터소스 CRUD API |
| `01_architecture/adapter-pattern.md` | 어댑터 패턴 설계 |
| `07_security/connection-security.md` | 연결 보안 |
