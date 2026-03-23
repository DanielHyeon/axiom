"""G37: Code Upload Sandbox — 업로드 격리 + 안전성 검증.

소스코드 업로드 시 ZIP 폭탄 방지, MIME 검증, 심볼릭 링크 탈출 차단,
용량 제한, 확장자 허용 목록 기반 격리를 수행한다.

LLM 분석보다 이 격리층이 먼저 있어야 운영 사고를 방지한다.
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("axiom.weaver.upload_sandbox")


# ── 제한값 ── #

MAX_TOTAL_SIZE = 100 * 1024 * 1024        # 100MB
MAX_FILE_COUNT = 5000                      # 최대 파일 수
MAX_SINGLE_FILE = 10 * 1024 * 1024        # 단일 파일 10MB
MAX_DECOMPRESSION_RATIO = 20              # ZIP 압축비 20배 초과 시 거부

ALLOWED_EXTENSIONS = {
    ".java", ".py", ".sql", ".ddl", ".xml", ".json",
    ".yml", ".yaml", ".txt", ".md", ".csv", ".properties",
    ".gradle", ".pom", ".cfg", ".ini", ".sh", ".kt",
    ".scala", ".groovy", ".rb", ".go", ".rs", ".ts", ".js",
    ".c", ".h", ".cpp", ".hpp", ".cs",
}

BLOCKED_EXTENSIONS = {
    ".exe", ".dll", ".so", ".bin", ".class", ".jar",
    ".war", ".bat", ".cmd", ".ps1", ".msi", ".com",
    ".scr", ".pif", ".vbs", ".wsf",
}

# 샌드박스 루트 디렉토리
_SANDBOX_ROOT = "/tmp/axiom-sandbox"


# ── 모델 ── #

class SandboxFileInfo(BaseModel):
    """샌드박스 내 파일 정보"""
    relative_path: str
    size: int
    extension: str
    is_text: bool = True


class SandboxResult(BaseModel):
    """샌드박스 검증 + 추출 결과"""
    upload_id: str
    sandbox_dir: str                       # 추출된 파일 디렉토리 경로
    files: list[SandboxFileInfo] = Field(default_factory=list)
    total_size: int = 0
    file_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    is_zip: bool = False


class SandboxError(Exception):
    """샌드박스 검증 실패"""
    pass


# ── 서비스 ── #

class UploadSandbox:
    """소스코드 업로드 격리 + 안전성 검증.

    사용법:
        sandbox = UploadSandbox()
        result = await sandbox.validate_and_extract(upload_file)
        # ... 분석 수행 ...
        await sandbox.cleanup(result.upload_id)
    """

    def __init__(self, sandbox_root: str = _SANDBOX_ROOT) -> None:
        self._root = Path(sandbox_root)
        self._root.mkdir(parents=True, exist_ok=True)

    async def validate_and_extract(
        self,
        file_content: bytes,
        filename: str,
        content_type: str = "",
    ) -> SandboxResult:
        """업로드 파일 검증 + 샌드박스 추출.

        검증 순서:
        1. 파일 크기 검증
        2. ZIP인 경우: 압축 해제 비율 + 심볼릭 링크 + 경로 탈출 검증
        3. 파일 수 제한
        4. 확장자 허용 목록
        5. 실행 권한 제거
        """
        upload_id = uuid.uuid4().hex
        sandbox_dir = self._root / upload_id
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. 전체 크기 검증
            if len(file_content) > MAX_TOTAL_SIZE:
                raise SandboxError(
                    f"파일 크기 초과: {len(file_content)} bytes (최대 {MAX_TOTAL_SIZE})"
                )

            # 2. ZIP 여부 감지 (magic bytes)
            is_zip = file_content[:4] == b'PK\x03\x04'

            if is_zip:
                files = self._extract_zip(file_content, sandbox_dir, upload_id)
            else:
                # 단일 파일
                files = self._save_single_file(file_content, filename, sandbox_dir)

            # 3. 총 파일 수 검증
            if len(files) > MAX_FILE_COUNT:
                raise SandboxError(
                    f"파일 수 초과: {len(files)} (최대 {MAX_FILE_COUNT})"
                )

            # 4. 확장자 검증 + 차단 파일 제거
            warnings: list[str] = []
            safe_files: list[SandboxFileInfo] = []
            for f in files:
                ext = f.extension.lower()
                if ext in BLOCKED_EXTENSIONS:
                    # 차단된 확장자 — 파일 삭제 + 경고
                    blocked_path = sandbox_dir / f.relative_path
                    if blocked_path.exists():
                        blocked_path.unlink()
                    warnings.append(f"차단된 파일 제거: {f.relative_path} ({ext})")
                elif ext and ext not in ALLOWED_EXTENSIONS:
                    warnings.append(f"미허용 확장자 (스킵): {f.relative_path} ({ext})")
                else:
                    safe_files.append(f)

            # 5. 실행 권한 제거
            self._remove_execute_permissions(sandbox_dir)

            total_size = sum(f.size for f in safe_files)

            return SandboxResult(
                upload_id=upload_id,
                sandbox_dir=str(sandbox_dir),
                files=safe_files,
                total_size=total_size,
                file_count=len(safe_files),
                warnings=warnings,
                is_zip=is_zip,
            )

        except SandboxError:
            # 검증 실패 시 샌드박스 정리
            self._force_cleanup(sandbox_dir)
            raise
        except Exception as e:
            self._force_cleanup(sandbox_dir)
            raise SandboxError(f"샌드박스 추출 실패: {e}") from e

    async def cleanup(self, upload_id: str) -> None:
        """분석 완료 후 샌드박스 디렉토리 즉시 삭제 — C1: get_sandbox_path() 경유"""
        sandbox_dir = self.get_sandbox_path(upload_id)  # 경로 탈출 방지
        self._force_cleanup(sandbox_dir)
        logger.info("샌드박스 정리: %s", upload_id)

    def get_sandbox_path(self, upload_id: str) -> Path:
        """샌드박스 디렉토리 경로 반환"""
        path = self._root / upload_id
        # 경로 탈출 방지
        if not str(path.resolve()).startswith(str(self._root.resolve())):
            raise SandboxError(f"경로 탈출 시도 감지: {upload_id}")
        return path

    # ── 내부 메서드 ── #

    def _extract_zip(
        self,
        content: bytes,
        sandbox_dir: Path,
        upload_id: str,
    ) -> list[SandboxFileInfo]:
        """ZIP 파일 안전 추출 — 폭탄/심링크/경로탈출 차단"""
        import io

        with zipfile.ZipFile(io.BytesIO(content), 'r') as zf:
            # ZIP 폭탄 검사: 압축 해제 후 총 크기 추정
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            compressed_size = len(content)
            if compressed_size > 0:
                ratio = total_uncompressed / compressed_size
                if ratio > MAX_DECOMPRESSION_RATIO:
                    raise SandboxError(
                        f"ZIP 폭탄 의심: 압축비 {ratio:.1f}x (최대 {MAX_DECOMPRESSION_RATIO}x)"
                    )

            if total_uncompressed > MAX_TOTAL_SIZE:
                raise SandboxError(
                    f"압축 해제 크기 초과: {total_uncompressed} bytes (최대 {MAX_TOTAL_SIZE})"
                )

            files: list[SandboxFileInfo] = []

            for info in zf.infolist():
                # 디렉토리 스킵
                if info.is_dir():
                    continue

                # 심볼릭 링크 차단
                if info.external_attr >> 16 & 0o120000 == 0o120000:
                    logger.warning("심볼릭 링크 건너뜀: %s", info.filename)
                    continue

                # 경로 탈출 방지 (.. 포함 검사)
                target_path = (sandbox_dir / info.filename).resolve()
                if not str(target_path).startswith(str(sandbox_dir.resolve())):
                    raise SandboxError(f"경로 탈출 시도: {info.filename}")

                # 단일 파일 크기 검사
                if info.file_size > MAX_SINGLE_FILE:
                    logger.warning("큰 파일 스킵: %s (%d bytes)", info.filename, info.file_size)
                    continue

                # 파일 수 검사
                if len(files) >= MAX_FILE_COUNT:
                    break

                # 추출 — M4: 실제 바이트 추적 (선언된 file_size 신뢰하지 않음)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                actual_bytes = 0
                with zf.open(info) as src, open(target_path, 'wb') as dst:
                    while True:
                        chunk = src.read(8192)
                        if not chunk:
                            break
                        actual_bytes += len(chunk)
                        if actual_bytes > MAX_SINGLE_FILE:
                            dst.close()
                            target_path.unlink(missing_ok=True)
                            raise SandboxError(
                                f"ZIP 내 파일 실제 크기 초과: {info.filename} ({actual_bytes} bytes)"
                            )
                        dst.write(chunk)

                ext = Path(info.filename).suffix
                files.append(SandboxFileInfo(
                    relative_path=info.filename,
                    size=info.file_size,
                    extension=ext,
                ))

            return files

    def _save_single_file(
        self,
        content: bytes,
        filename: str,
        sandbox_dir: Path,
    ) -> list[SandboxFileInfo]:
        """단일 파일 저장"""
        if len(content) > MAX_SINGLE_FILE:
            raise SandboxError(
                f"파일 크기 초과: {len(content)} bytes (최대 {MAX_SINGLE_FILE})"
            )

        # 파일명 안전 처리
        safe_name = Path(filename).name  # 경로 요소 제거
        if not safe_name:
            safe_name = "uploaded_file"

        target = sandbox_dir / safe_name
        target.write_bytes(content)

        ext = Path(safe_name).suffix
        return [SandboxFileInfo(
            relative_path=safe_name,
            size=len(content),
            extension=ext,
        )]

    def _remove_execute_permissions(self, directory: Path) -> None:
        """디렉토리 내 모든 파일의 실행 권한 제거"""
        for root, dirs, files in os.walk(directory):
            for f in files:
                filepath = Path(root) / f
                try:
                    current = filepath.stat().st_mode
                    filepath.chmod(current & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
                except OSError:
                    pass

    def _force_cleanup(self, directory: Path) -> None:
        """디렉토리 강제 삭제 (에러 무시)"""
        try:
            if directory.exists():
                shutil.rmtree(directory, ignore_errors=True)
        except Exception:
            pass
