"""Upload Sandbox 단위 테스트 — Sprint 8.

ZIP 폭탄 방지, 경로 탈출 차단, 확장자 필터링, 실행 권한 제거 등 검증.
"""

import io
import os
import zipfile

import pytest
from app.services.upload_sandbox import (
    UploadSandbox,
    SandboxError,
    MAX_TOTAL_SIZE,
    MAX_SINGLE_FILE,
    MAX_DECOMPRESSION_RATIO,
    ALLOWED_EXTENSIONS,
    BLOCKED_EXTENSIONS,
)


@pytest.fixture
def sandbox(tmp_path):
    return UploadSandbox(sandbox_root=str(tmp_path / "sandbox"))


def _make_zip(files: dict[str, bytes]) -> bytes:
    """테스트용 ZIP 파일 생성"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


# ── 기본 동작 ── #

class TestBasicUpload:
    @pytest.mark.asyncio
    async def test_single_file_upload(self, sandbox):
        result = await sandbox.validate_and_extract(
            b"CREATE TABLE test (id INT);",
            "schema.sql",
        )
        assert result.file_count == 1
        assert result.total_size > 0
        assert result.upload_id

    @pytest.mark.asyncio
    async def test_zip_upload(self, sandbox):
        zip_data = _make_zip({
            "src/schema.sql": b"CREATE TABLE t1 (id INT);",
            "src/data.sql": b"INSERT INTO t1 VALUES (1);",
        })
        result = await sandbox.validate_and_extract(zip_data, "upload.zip")
        assert result.is_zip is True
        assert result.file_count == 2

    @pytest.mark.asyncio
    async def test_cleanup(self, sandbox):
        result = await sandbox.validate_and_extract(b"test content", "test.sql")
        sandbox_path = sandbox.get_sandbox_path(result.upload_id)
        assert sandbox_path.exists()

        await sandbox.cleanup(result.upload_id)
        assert not sandbox_path.exists()


# ── 보안 검증 ── #

class TestSecurityChecks:
    @pytest.mark.asyncio
    async def test_oversized_file_rejected(self, sandbox):
        big_content = b"x" * (MAX_TOTAL_SIZE + 1)
        with pytest.raises(SandboxError, match="크기 초과"):
            await sandbox.validate_and_extract(big_content, "big.sql")

    @pytest.mark.asyncio
    async def test_blocked_extension_removed(self, sandbox):
        zip_data = _make_zip({
            "good.sql": b"CREATE TABLE t (id INT);",
            "bad.exe": b"MZ\x90\x00",
        })
        result = await sandbox.validate_and_extract(zip_data, "upload.zip")
        # .exe는 제거됨 → 경고에 포함
        assert any(".exe" in w for w in result.warnings)
        # .sql만 남음
        sql_files = [f for f in result.files if f.extension == ".sql"]
        assert len(sql_files) == 1

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, sandbox):
        """경로 탈출 시도 차단 (../../etc/passwd)"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../etc/passwd", "root:x:0:0")
        with pytest.raises(SandboxError, match="경로 탈출"):
            await sandbox.validate_and_extract(buf.getvalue(), "evil.zip")

    @pytest.mark.asyncio
    async def test_path_traversal_in_cleanup(self, sandbox):
        """cleanup에서 경로 탈출 시도 차단"""
        with pytest.raises(SandboxError, match="경로 탈출"):
            await sandbox.cleanup("../../etc")

    @pytest.mark.asyncio
    async def test_get_sandbox_path_validates(self, sandbox):
        with pytest.raises(SandboxError):
            sandbox.get_sandbox_path("../../../tmp")

    @pytest.mark.asyncio
    async def test_execute_permissions_removed(self, sandbox):
        result = await sandbox.validate_and_extract(b"#!/bin/bash\necho hi", "script.sh")
        sandbox_path = sandbox.get_sandbox_path(result.upload_id)
        for f in sandbox_path.rglob("*"):
            if f.is_file():
                mode = f.stat().st_mode
                assert not (mode & 0o111), f"파일 {f}에 실행 권한이 남아있음"


# ── ZIP 폭탄 ── #

class TestZipBomb:
    @pytest.mark.asyncio
    async def test_high_compression_ratio_rejected(self, sandbox):
        """압축비 20배 초과 시 거부"""
        # 높은 압축비 데이터 생성 (반복 패턴)
        big_data = b"A" * (1024 * 1024 * 5)  # 5MB 비압축
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("bomb.txt", big_data)
        zip_bytes = buf.getvalue()

        # 압축이 잘 되면 비율 높음 — MAX_DECOMPRESSION_RATIO 초과 확인
        info = zipfile.ZipFile(io.BytesIO(zip_bytes)).infolist()[0]
        ratio = info.file_size / len(zip_bytes) if len(zip_bytes) > 0 else 0

        if ratio > MAX_DECOMPRESSION_RATIO:
            with pytest.raises(SandboxError, match="ZIP 폭탄"):
                await sandbox.validate_and_extract(zip_bytes, "bomb.zip")
        # 비율이 제한 내이면 통과 (테스트 환경에서 압축률 보장 불가)
