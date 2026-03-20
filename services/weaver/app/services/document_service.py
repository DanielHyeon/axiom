"""DocumentService — 문서 업로드 + 텍스트 추출 + 청킹 (Phase 2-E).

지원 파일 형식:
  - PDF  : pypdf 라이브러리 (설치 안 된 경우 fallback으로 raw 바이트 디코딩)
  - DOCX : python-docx 라이브러리 (설치 안 된 경우 빈 텍스트)
  - TXT / MD : UTF-8 직접 읽기

청킹 전략:
  - 페이지 기반 분할 (PDF) 또는 고정 길이 분할 (~1200자)
  - 각 청크에 page, span_start, span_end 메타데이터 부여

DB 패턴: asyncpg pool (document_schema._get_pool)
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any

from app.db.document_schema import get_document_pool

logger = logging.getLogger("axiom.weaver.document_service")

# 텍스트 청킹 최대 길이
_CHUNK_SIZE = 1200


class DocumentService:
    """문서 업로드 → 텍스트 추출 → 청킹 → DB 저장 서비스."""

    # ── 공개 API ──────────────────────────────────────────────── #

    async def upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        file_type: str,
        case_id: str = "",
        tenant_id: str = "",
    ) -> dict[str, Any]:
        """문서를 저장하고 텍스트를 추출·청킹하여 DB에 기록한다.

        Returns:
            doc_id, filename, file_type, page_count, fragment_count, status
        """
        doc_id = f"doc-{uuid.uuid4().hex[:12]}"
        file_type_norm = self._normalize_file_type(filename, file_type)

        # 1) 임시 파일에 저장 (실제 프로덕션에서는 S3 등 오브젝트 스토어 사용)
        storage_path = self._save_to_temp(doc_id, filename, file_bytes)

        # 2) 텍스트 추출
        pages = self._extract_text(file_bytes, file_type_norm)
        page_count = len(pages)

        # 3) 텍스트 청킹
        fragments = self._chunk_pages(pages, doc_id)

        # 4) DB 저장
        pool = await get_document_pool()
        async with pool.acquire() as conn:
            # 트랜잭션으로 문서 + 프래그먼트 일괄 저장
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO weaver.documents
                        (id, case_id, tenant_id, filename, file_type,
                         file_size, page_count, status, storage_path)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    doc_id, case_id, tenant_id, filename, file_type_norm,
                    len(file_bytes), page_count, "uploaded", storage_path,
                )

                # 프래그먼트 일괄 삽입
                if fragments:
                    await conn.executemany(
                        """
                        INSERT INTO weaver.doc_fragments
                            (id, doc_id, page, span_start, span_end, text)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        [
                            (f["id"], doc_id, f["page"],
                             f["span_start"], f["span_end"], f["text"])
                            for f in fragments
                        ],
                    )

        logger.info(
            "문서 업로드 완료: doc_id=%s, filename=%s, pages=%d, fragments=%d",
            doc_id, filename, page_count, len(fragments),
        )

        return {
            "doc_id": doc_id,
            "filename": filename,
            "file_type": file_type_norm,
            "page_count": page_count,
            "fragment_count": len(fragments),
            "status": "uploaded",
        }

    async def get_document(self, doc_id: str, tenant_id: str = "") -> dict[str, Any] | None:
        """문서 메타데이터 조회 (tenant_id로 데이터 격리)."""
        pool = await get_document_pool()
        async with pool.acquire() as conn:
            if tenant_id:
                row = await conn.fetchrow(
                    "SELECT * FROM weaver.documents WHERE id = $1 AND tenant_id = $2",
                    doc_id, tenant_id,
                )
            else:
                row = await conn.fetchrow(
                    "SELECT * FROM weaver.documents WHERE id = $1", doc_id,
                )
        if row is None:
            return None
        return dict(row)

    async def get_fragments(self, doc_id: str, tenant_id: str = "") -> list[dict[str, Any]]:
        """문서의 모든 프래그먼트 조회 (페이지 순, tenant_id로 데이터 격리)."""
        pool = await get_document_pool()
        async with pool.acquire() as conn:
            if tenant_id:
                # tenant_id 격리: 해당 테넌트 소유 문서의 프래그먼트만 반환
                rows = await conn.fetch(
                    """
                    SELECT f.id, f.doc_id, f.page, f.span_start, f.span_end,
                           f.text, f.created_at
                    FROM weaver.doc_fragments f
                    JOIN weaver.documents d ON d.id = f.doc_id
                    WHERE f.doc_id = $1 AND d.tenant_id = $2
                    ORDER BY f.page ASC, f.span_start ASC
                    """,
                    doc_id, tenant_id,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, doc_id, page, span_start, span_end, text, created_at
                    FROM weaver.doc_fragments
                    WHERE doc_id = $1
                    ORDER BY page ASC, span_start ASC
                    """,
                    doc_id,
                )
        return [dict(r) for r in rows]

    # ── 추출 잡 관련 DB 헬퍼 ──────────────────────────────────── #

    async def create_extraction_job(
        self,
        doc_id: str,
        case_id: str,
        tenant_id: str,
    ) -> str:
        """추출 잡을 생성하고 job_id를 반환한다."""
        job_id = f"exjob-{uuid.uuid4().hex[:12]}"
        pool = await get_document_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO weaver.extraction_jobs
                    (id, doc_id, case_id, tenant_id, status, progress)
                VALUES ($1, $2, $3, $4, 'queued', 0)
                """,
                job_id, doc_id, case_id, tenant_id,
            )
        return job_id

    async def update_job_progress(
        self,
        job_id: str,
        status: str,
        progress: int,
        result: dict | None = None,
        error: str | None = None,
    ) -> None:
        """추출 잡 진행 상태 업데이트."""
        pool = await get_document_pool()
        async with pool.acquire() as conn:
            completed = (
                datetime.now(timezone.utc) if status in ("done", "error") else None
            )
            result_json = json.dumps(result, ensure_ascii=False) if result else None
            await conn.execute(
                """
                UPDATE weaver.extraction_jobs
                SET status = $1, progress = $2, result = $3::jsonb,
                    error = $4, completed_at = $5
                WHERE id = $6
                """,
                status, progress, result_json, error, completed, job_id,
            )

    async def get_job(self, job_id: str, tenant_id: str = "") -> dict[str, Any] | None:
        """추출 잡 상태 조회 (tenant_id로 데이터 격리)."""
        pool = await get_document_pool()
        async with pool.acquire() as conn:
            if tenant_id:
                row = await conn.fetchrow(
                    "SELECT * FROM weaver.extraction_jobs WHERE id = $1 AND tenant_id = $2",
                    job_id, tenant_id,
                )
            else:
                row = await conn.fetchrow(
                    "SELECT * FROM weaver.extraction_jobs WHERE id = $1", job_id,
                )
        if row is None:
            return None
        result = dict(row)
        # JSONB 컬럼은 자동 파싱되지만, 문자열인 경우 안전하게 처리
        if isinstance(result.get("result"), str):
            try:
                result["result"] = json.loads(result["result"])
            except (json.JSONDecodeError, TypeError):
                pass
        return result

    # ── 내부 헬퍼 ─────────────────────────────────────────────── #

    @staticmethod
    def _normalize_file_type(filename: str, file_type: str) -> str:
        """파일 확장자 기반으로 파일 타입을 정규화한다."""
        if file_type and file_type.lower() in ("pdf", "docx", "txt", "md"):
            return file_type.lower()
        # content_type 기반 추론
        ct = file_type.lower() if file_type else ""
        if "pdf" in ct:
            return "pdf"
        if "wordprocessingml" in ct or "docx" in ct:
            return "docx"
        if "markdown" in ct or "md" in ct:
            return "md"
        # 확장자 기반 추론
        ext = os.path.splitext(filename)[1].lower().lstrip(".")
        if ext in ("pdf", "docx", "txt", "md"):
            return ext
        return "txt"

    @staticmethod
    def _save_to_temp(doc_id: str, filename: str, data: bytes) -> str:
        """임시 디렉토리에 파일 저장 (개발용, 프로덕션에서는 S3 교체).

        보안: 파일명을 sanitize하여 경로 순회(path traversal) 공격을 방지한다.
        """
        import re as _re

        temp_dir = os.path.join(tempfile.gettempdir(), "axiom_documents")
        os.makedirs(temp_dir, exist_ok=True)
        # 파일명에서 디렉토리 구분자와 위험 문자를 제거
        safe_name = f"{doc_id}_{_re.sub(r'[^a-zA-Z0-9._-]', '_', os.path.basename(filename))}"
        path = os.path.join(temp_dir, safe_name)
        # 최종 경로가 temp_dir 내부인지 확인 (경로 순회 방지)
        if not os.path.realpath(path).startswith(os.path.realpath(temp_dir)):
            raise ValueError("Invalid filename")
        with open(path, "wb") as f:
            f.write(data)
        return path

    @staticmethod
    def _extract_text(file_bytes: bytes, file_type: str) -> list[str]:
        """파일 바이트에서 페이지별 텍스트를 추출한다.

        Returns:
            페이지별 텍스트 리스트 (페이지 개념이 없으면 전체를 1개 페이지로)
        """
        if file_type == "pdf":
            return DocumentService._extract_pdf(file_bytes)
        if file_type == "docx":
            return DocumentService._extract_docx(file_bytes)
        # TXT / MD: UTF-8로 직접 읽기
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = file_bytes.decode("utf-8", errors="replace")
        return [text] if text.strip() else []

    @staticmethod
    def _extract_pdf(file_bytes: bytes) -> list[str]:
        """PDF에서 페이지별 텍스트 추출. pypdf가 없으면 fallback."""
        try:
            import pypdf
            import io

            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            pages: list[str] = []
            for page in reader.pages:
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(text)
            if pages:
                return pages
        except ImportError:
            logger.warning("pypdf 미설치 — PDF fallback 모드 사용")
        except Exception as exc:
            logger.warning("pypdf 텍스트 추출 실패: %s — fallback 시도", exc)

        # Fallback: raw 바이트에서 텍스트 추출 시도
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            # PDF 바이너리에서 의미 있는 텍스트만 추출
            cleaned = "".join(ch for ch in text if ch.isprintable() or ch in "\n\t")
            return [cleaned] if cleaned.strip() else ["[PDF 텍스트 추출 실패]"]
        except Exception:
            return ["[PDF 텍스트 추출 실패]"]

    @staticmethod
    def _extract_docx(file_bytes: bytes) -> list[str]:
        """DOCX에서 텍스트 추출. python-docx가 없으면 빈 결과."""
        try:
            from docx import Document
            import io

            doc = Document(io.BytesIO(file_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            if paragraphs:
                # DOCX는 페이지 개념이 명확하지 않으므로 전체를 1 페이지로 처리
                return ["\n".join(paragraphs)]
            return []
        except ImportError:
            logger.warning("python-docx 미설치 — DOCX 텍스트 추출 불가")
            return ["[DOCX 텍스트 추출 불가 — python-docx 미설치]"]
        except Exception as exc:
            logger.warning("DOCX 텍스트 추출 실패: %s", exc)
            return ["[DOCX 텍스트 추출 실패]"]

    @staticmethod
    def _chunk_pages(pages: list[str], doc_id: str) -> list[dict[str, Any]]:
        """페이지별 텍스트를 ~1200자 단위로 청킹한다.

        각 청크에 page, span_start, span_end 메타데이터를 부여한다.
        """
        fragments: list[dict[str, Any]] = []
        for page_idx, page_text in enumerate(pages):
            page_num = page_idx + 1
            offset = 0
            while offset < len(page_text):
                # 1200자 기준이지만, 문장 경계에서 끊기 시도
                end = min(offset + _CHUNK_SIZE, len(page_text))
                if end < len(page_text):
                    # 마지막 마침표·줄바꿈 위치에서 끊기
                    for sep in ["\n\n", "\n", ". ", "。", "? ", "! "]:
                        last_sep = page_text.rfind(sep, offset + 200, end)
                        if last_sep > offset:
                            end = last_sep + len(sep)
                            break

                chunk_text = page_text[offset:end].strip()
                if chunk_text:
                    frag_id = f"frag-{uuid.uuid4().hex[:12]}"
                    fragments.append({
                        "id": frag_id,
                        "doc_id": doc_id,
                        "page": page_num,
                        "span_start": offset,
                        "span_end": end,
                        "text": chunk_text,
                    })
                offset = end

        return fragments


# 싱글톤 인스턴스
document_service = DocumentService()
