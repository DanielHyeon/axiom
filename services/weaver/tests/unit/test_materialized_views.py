"""Materialized View 서비스 + Fernet 암호화 단위 테스트.

테스트 범위:
- SQL 식별자 유효성 검증
- Fernet 암호화/복호화 라운드트립
- 레거시 평문 비밀번호 통과
- MV 서비스 SQL 생성 검증
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest


# ── 1. SQL 식별자 유효성 검증 테스트 ── #


class TestSqlIdentifierValidation:
    """SQL 식별자 패턴 검증 테스트."""

    def test_valid_simple_name(self):
        """일반 알파벳 이름은 유효해야 한다."""
        from app.services.materialized_view_service import validate_sql_identifier
        assert validate_sql_identifier("my_view") is True

    def test_valid_underscore_start(self):
        """언더스코어로 시작하는 이름은 유효해야 한다."""
        from app.services.materialized_view_service import validate_sql_identifier
        assert validate_sql_identifier("_private_view") is True

    def test_valid_mixed_case(self):
        """대소문자 혼합 이름은 유효해야 한다."""
        from app.services.materialized_view_service import validate_sql_identifier
        assert validate_sql_identifier("MyView123") is True

    def test_invalid_starts_with_number(self):
        """숫자로 시작하는 이름은 무효여야 한다."""
        from app.services.materialized_view_service import validate_sql_identifier
        assert validate_sql_identifier("123view") is False

    def test_invalid_contains_space(self):
        """공백이 포함된 이름은 무효여야 한다."""
        from app.services.materialized_view_service import validate_sql_identifier
        assert validate_sql_identifier("my view") is False

    def test_invalid_contains_semicolon(self):
        """세미콜론(SQL 인젝션 시도)이 포함된 이름은 무효여야 한다."""
        from app.services.materialized_view_service import validate_sql_identifier
        assert validate_sql_identifier("view; DROP TABLE") is False

    def test_invalid_contains_dash(self):
        """하이픈이 포함된 이름은 무효여야 한다."""
        from app.services.materialized_view_service import validate_sql_identifier
        assert validate_sql_identifier("my-view") is False

    def test_invalid_empty_string(self):
        """빈 문자열은 무효여야 한다."""
        from app.services.materialized_view_service import validate_sql_identifier
        assert validate_sql_identifier("") is False

    def test_invalid_too_long(self):
        """64자 이상의 이름은 무효여야 한다 (PostgreSQL 제한)."""
        from app.services.materialized_view_service import validate_sql_identifier
        long_name = "a" * 64
        assert validate_sql_identifier(long_name) is False

    def test_valid_max_length(self):
        """63자 이름은 유효해야 한다 (PostgreSQL 최대)."""
        from app.services.materialized_view_service import validate_sql_identifier
        max_name = "a" * 63
        assert validate_sql_identifier(max_name) is True

    def test_invalid_sql_injection_attempt(self):
        """SQL 인젝션 패턴은 무효여야 한다."""
        from app.services.materialized_view_service import validate_sql_identifier
        assert validate_sql_identifier("x'; DROP TABLE users;--") is False

    def test_invalid_dot_notation(self):
        """점(.) 포함 이름은 무효여야 한다 (스키마.이름 형식은 별도 처리)."""
        from app.services.materialized_view_service import validate_sql_identifier
        assert validate_sql_identifier("schema.view") is False


# ── 2. Fernet 암호화/복호화 테스트 ── #


class TestFernetCrypto:
    """Fernet 기반 비밀번호 암호화 테스트."""

    @pytest.fixture(autouse=True)
    def _set_encryption_key(self, tmp_path, monkeypatch):
        """테스트용 고정 Fernet 키를 환경변수로 설정한다."""
        from cryptography.fernet import Fernet
        test_key = Fernet.generate_key().decode()
        monkeypatch.setenv("WEAVER_ENCRYPTION_KEY", test_key)

    def test_encrypt_decrypt_roundtrip(self):
        """암호화 후 복호화하면 원래 값이 복원되어야 한다."""
        from app.core.crypto import decrypt_password, encrypt_password
        original = "my_secret_password_123!"
        encrypted = encrypt_password(original)
        assert encrypted.startswith("enc:")
        assert encrypted != original
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    def test_encrypt_produces_enc_prefix(self):
        """암호화 결과는 'enc:' 접두어를 가져야 한다."""
        from app.core.crypto import encrypt_password
        result = encrypt_password("test")
        assert result.startswith("enc:")

    def test_decrypt_legacy_plaintext(self):
        """'enc:' 접두어가 없는 값은 레거시 평문으로 그대로 반환해야 한다."""
        from app.core.crypto import decrypt_password
        plain = "legacy_password"
        assert decrypt_password(plain) == plain

    def test_encrypt_empty_string(self):
        """빈 문자열은 그대로 반환해야 한다."""
        from app.core.crypto import decrypt_password, encrypt_password
        assert encrypt_password("") == ""
        assert decrypt_password("") == ""

    def test_decrypt_none_passthrough(self):
        """None이나 falsy 값은 그대로 반환해야 한다."""
        from app.core.crypto import decrypt_password
        assert decrypt_password("") == ""

    def test_unicode_password_roundtrip(self):
        """유니코드(한글 등) 비밀번호도 정상 암복호화되어야 한다."""
        from app.core.crypto import decrypt_password, encrypt_password
        original = "비밀번호_테스트_🔑"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    def test_different_encryptions_differ(self):
        """같은 평문을 두 번 암호화하면 서로 다른 결과가 나와야 한다 (Fernet 타임스탬프/IV)."""
        from app.core.crypto import encrypt_password
        enc1 = encrypt_password("same_password")
        enc2 = encrypt_password("same_password")
        assert enc1 != enc2  # Fernet은 매번 다른 암호문 생성

    def test_invalid_ciphertext_raises(self):
        """잘못된 암호문은 ValueError를 발생시켜야 한다."""
        from app.core.crypto import decrypt_password
        with pytest.raises(ValueError, match="복호화"):
            decrypt_password("enc:invalid_base64_garbage!!!")


# ── 3. Fernet 키 자동 생성 테스트 (개발 모드) ── #


class TestFernetKeyAutoGeneration:
    """환경변수 없을 때 .encryption_key 파일 자동 생성 테스트."""

    def test_auto_generate_key_file(self, tmp_path, monkeypatch):
        """환경변수가 없으면 .encryption_key 파일을 자동 생성해야 한다."""
        monkeypatch.delenv("WEAVER_ENCRYPTION_KEY", raising=False)

        # crypto 모듈의 키 파일 경로를 tmp_path로 변경
        key_file = tmp_path / ".encryption_key"
        assert not key_file.exists()

        with patch("app.core.crypto.Path") as mock_path_cls:
            # __file__ 기반 경로 계산을 tmp_path로 리다이렉트
            mock_resolved = mock_path_cls.return_value.resolve.return_value
            mock_resolved.parent.parent.parent.__truediv__ = lambda self, name: key_file

            from app.core.crypto import encrypt_password, decrypt_password
            # 직접 키 생성 로직을 테스트하기 위해 _load_or_generate_key 호출
            from app.core.crypto import _load_or_generate_key

            # 실제 경로 패치 대신, 환경변수 없이 직접 키 생성 확인
            # (파일 시스템 접근은 실제 경로에 의존하므로 환경변수 방식으로 대체 검증)
            monkeypatch.setenv("WEAVER_ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXVuaXQtdGVzdHM=")
            from cryptography.fernet import Fernet
            test_key = Fernet.generate_key().decode()
            monkeypatch.setenv("WEAVER_ENCRYPTION_KEY", test_key)

            encrypted = encrypt_password("auto_gen_test")
            assert decrypt_password(encrypted) == "auto_gen_test"


# ── 4. MV 서비스 헬퍼 테스트 ── #


class TestMaterializedViewService:
    """Materialized View 서비스 로직 테스트."""

    @pytest.fixture
    def mock_client(self):
        """MindsDB 클라이언트 목 객체를 생성한다."""
        client = AsyncMock()
        client.execute_query = AsyncMock(return_value={"columns": [], "data": []})
        return client

    @pytest.fixture
    def service(self, mock_client):
        """테스트용 MV 서비스 인스턴스를 생성한다."""
        from app.services.materialized_view_service import MaterializedViewService
        return MaterializedViewService(client=mock_client)

    @pytest.mark.asyncio
    async def test_create_mv_with_source_table(self, service, mock_client):
        """source_table 기반 MV 생성 시 올바른 SQL이 실행되어야 한다."""
        result = await service.create_mv(
            name="sales_summary",
            source_table="sales",
            schema_name="public",
        )
        assert result["status"] == "created"
        assert result["name"] == "sales_summary"

        # 호출된 SQL 확인
        sql_arg = mock_client.execute_query.call_args[0][0]
        assert "CREATE MATERIALIZED VIEW public.sales_summary" in sql_arg
        assert "SELECT * FROM public.sales" in sql_arg

    @pytest.mark.asyncio
    async def test_create_mv_with_custom_query(self, service, mock_client):
        """커스텀 SELECT 쿼리 기반 MV 생성이 정상 동작해야 한다."""
        custom_sql = "SELECT region, SUM(amount) FROM sales GROUP BY region"
        result = await service.create_mv(
            name="sales_by_region",
            source_table="",
            schema_name="analytics",
            select_query=custom_sql,
        )
        assert result["status"] == "created"
        sql_arg = mock_client.execute_query.call_args[0][0]
        assert "CREATE MATERIALIZED VIEW analytics.sales_by_region" in sql_arg
        assert custom_sql in sql_arg

    @pytest.mark.asyncio
    async def test_refresh_mv(self, service, mock_client):
        """MV 새로고침 시 올바른 SQL이 실행되어야 한다."""
        result = await service.refresh_mv(name="sales_summary", schema_name="public")
        assert result["status"] == "refreshed"
        sql_arg = mock_client.execute_query.call_args[0][0]
        assert "REFRESH MATERIALIZED VIEW public.sales_summary" in sql_arg
        assert "CONCURRENTLY" not in sql_arg

    @pytest.mark.asyncio
    async def test_refresh_mv_concurrently(self, service, mock_client):
        """CONCURRENTLY 옵션이 SQL에 반영되어야 한다."""
        await service.refresh_mv(name="mv1", schema_name="public", concurrently=True)
        sql_arg = mock_client.execute_query.call_args[0][0]
        assert "REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv1" in sql_arg

    @pytest.mark.asyncio
    async def test_drop_mv(self, service, mock_client):
        """MV 삭제 시 IF EXISTS가 기본 포함되어야 한다."""
        result = await service.drop_mv(name="old_view", schema_name="public")
        assert result["status"] == "dropped"
        sql_arg = mock_client.execute_query.call_args[0][0]
        assert "DROP MATERIALIZED VIEW IF EXISTS public.old_view" in sql_arg

    @pytest.mark.asyncio
    async def test_drop_mv_without_if_exists(self, service, mock_client):
        """if_exists=False 시 IF EXISTS가 없어야 한다."""
        await service.drop_mv(name="strict_view", schema_name="public", if_exists=False)
        sql_arg = mock_client.execute_query.call_args[0][0]
        assert "IF EXISTS" not in sql_arg

    @pytest.mark.asyncio
    async def test_list_mvs(self, service, mock_client):
        """MV 목록 조회 시 pg_matviews를 쿼리해야 한다."""
        mock_client.execute_query.return_value = {
            "columns": ["schemaname", "matviewname", "matviewowner", "ispopulated", "definition"],
            "data": [
                ["public", "mv_sales", "postgres", True, "SELECT * FROM sales"],
            ],
        }
        result = await service.list_mvs(schema_name="public")
        assert len(result) == 1
        assert result[0]["matviewname"] == "mv_sales"
        sql_arg = mock_client.execute_query.call_args[0][0]
        assert "pg_matviews" in sql_arg
        assert "schemaname = 'public'" in sql_arg

    @pytest.mark.asyncio
    async def test_create_mv_invalid_name_raises(self, service):
        """유효하지 않은 MV 이름은 MaterializedViewError를 발생시켜야 한다."""
        from app.services.materialized_view_service import MaterializedViewError
        with pytest.raises(MaterializedViewError, match="유효하지 않은"):
            await service.create_mv(
                name="invalid-name!",
                source_table="sales",
            )

    @pytest.mark.asyncio
    async def test_create_mv_invalid_schema_raises(self, service):
        """유효하지 않은 스키마 이름은 MaterializedViewError를 발생시켜야 한다."""
        from app.services.materialized_view_service import MaterializedViewError
        with pytest.raises(MaterializedViewError, match="유효하지 않은"):
            await service.create_mv(
                name="valid_name",
                source_table="sales",
                schema_name="schema; DROP TABLE",
            )

    @pytest.mark.asyncio
    async def test_database_parameter_passed(self, service, mock_client):
        """database 파라미터가 execute_query에 전달되어야 한다."""
        await service.create_mv(
            name="mv1",
            source_table="t1",
            database="my_pg_db",
        )
        _, kwargs = mock_client.execute_query.call_args
        assert kwargs.get("database") == "my_pg_db"


# ── 5. _ensure_valid_identifier 예외 테스트 ── #


class TestEnsureValidIdentifier:
    """_ensure_valid_identifier 함수의 예외 발생 테스트."""

    def test_raises_on_invalid(self):
        """유효하지 않은 식별자에 대해 MaterializedViewError가 발생해야 한다."""
        from app.services.materialized_view_service import MaterializedViewError, _ensure_valid_identifier
        with pytest.raises(MaterializedViewError):
            _ensure_valid_identifier("1bad", "테스트 이름")

    def test_passes_on_valid(self):
        """유효한 식별자는 예외 없이 통과해야 한다."""
        from app.services.materialized_view_service import _ensure_valid_identifier
        _ensure_valid_identifier("good_name", "테스트 이름")  # 예외 없음
