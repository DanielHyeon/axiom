"""소스코드 업로드 + 파일 타입 감지 + DDL 분석 + LLM 코드 분석 API.

Sprint 5: 업로드, 타입 감지, DDL 파싱
Sprint 6: LLM 코드 분석(G01a), Evidence(G34)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.auth import AuthService, CurrentUser
from app.jobs.job_service import job_service
from app.models.job import JobType
from app.services.upload_sandbox import UploadSandbox, SandboxError, SandboxResult
from app.services.file_type_detector import FileTypeDetector, FileTypeDetectionResult
from app.services.parsers.ddl_parser import DDLParser
from app.services.parsers.ddl_models import DDLParseResult
from app.services.code_analyzer import CodeAnalyzer
from app.services.code_lineage import CodeLineageExtractor
from app.models.evidence import evidence_store

logger = logging.getLogger("axiom.weaver.api.code_upload")

router = APIRouter(prefix="/api/v3/weaver/code", tags=["code-analysis"])

# C2: upload_id 형식 검증 (uuid4.hex = 32자 hex)
import re as _re
_UPLOAD_ID_PATTERN = _re.compile(r"^[a-f0-9]{32}$")


def _validate_upload_id(upload_id: str) -> str:
    """upload_id 형식 검증 — 경로 탈출 방지"""
    if not _UPLOAD_ID_PATTERN.match(upload_id):
        raise HTTPException(status_code=400, detail="유효하지 않은 upload_id 형식")
    return upload_id

_auth = AuthService()
_sandbox = UploadSandbox()
_detector = FileTypeDetector()
_analyzer = CodeAnalyzer()
_lineage_extractor = CodeLineageExtractor()

_ALLOWED_ROLES = {"admin", "analyst", "engineer", "manager"}


async def _get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    return _auth.verify_token(authorization)


# ── 응답 모델 ── #

class CodeUploadResponse(BaseModel):
    success: bool = True
    upload_id: str
    file_count: int
    total_size: int
    warnings: list[str] = Field(default_factory=list)
    job_run_id: str = ""


class DDLAnalysisResponse(BaseModel):
    success: bool = True
    upload_id: str
    tables_found: int
    parse_errors: int
    tables: list[dict] = Field(default_factory=list)  # 간략 테이블 정보
    errors: list[str] = Field(default_factory=list)


# ── 엔드포인트 ── #

@router.post("/upload")
async def upload_source_files(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(_get_current_user),
) -> CodeUploadResponse:
    """소스코드 파일 업로드 (ZIP/개별 파일).

    1. UploadSandbox로 격리 + 안전성 검증 (G37)
    2. JobRun 레코드 생성 (G35)
    3. upload_id 반환
    """
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="코드 업로드는 analyst 이상만 가능합니다")

    try:
        # M5: 조기 크기 차단 (100MB + 1 byte)
        max_upload = 100 * 1024 * 1024
        content = await file.read(max_upload + 1)
        if len(content) > max_upload:
            raise HTTPException(status_code=413, detail=f"파일 크기 초과 (최대 {max_upload // (1024*1024)}MB)")

        result = await _sandbox.validate_and_extract(
            file_content=content,
            filename=file.filename or "upload",
            content_type=file.content_type or "",
        )

        # JobRun 레코드 생성
        job = await job_service.create(
            job_type=JobType.CODE_ANALYSIS,
            tenant_id=user.tenant_id,
            triggered_by=user.user_id,
            idempotency_key=f"upload:{result.upload_id}",
        )

        logger.info(
            "코드 업로드 완료: upload_id=%s, files=%d, size=%d",
            result.upload_id, result.file_count, result.total_size,
        )

        return CodeUploadResponse(
            upload_id=result.upload_id,
            file_count=result.file_count,
            total_size=result.total_size,
            warnings=result.warnings,
            job_run_id=job.run_id,
        )

    except SandboxError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("코드 업로드 실패: %s", e)
        raise HTTPException(status_code=500, detail="코드 업로드 중 내부 오류 발생") from e


@router.post("/{upload_id}/detect-types")
async def detect_file_types(
    upload_id: str,
    user: CurrentUser = Depends(_get_current_user),
) -> FileTypeDetectionResult:
    """업로드된 파일의 언어/프레임워크 자동 감지 (G25).

    확장자 1차 → 내용 패턴 2차 → 전략/타겟 추천.
    """
    _validate_upload_id(upload_id)
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")

    try:
        sandbox_dir = _sandbox.get_sandbox_path(upload_id)
        if not sandbox_dir.exists():
            raise HTTPException(status_code=404, detail=f"업로드를 찾을 수 없습니다: {upload_id}")

        # 파일 목록 재구성 (샌드박스에서)
        from app.services.upload_sandbox import SandboxFileInfo
        files = []
        for p in sandbox_dir.rglob("*"):
            if p.is_file():
                rel = str(p.relative_to(sandbox_dir))
                files.append(SandboxFileInfo(
                    relative_path=rel,
                    size=p.stat().st_size,
                    extension=p.suffix,
                ))

        result = _detector.detect(upload_id, files, str(sandbox_dir))
        return result

    except HTTPException:
        raise
    except SandboxError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("파일 타입 감지 실패: %s", e)
        raise HTTPException(status_code=500, detail="파일 타입 감지 중 내부 오류 발생") from e


@router.post("/{upload_id}/analyze-ddl")
async def analyze_ddl_files(
    upload_id: str,
    dialect: str = "postgresql",
    user: CurrentUser = Depends(_get_current_user),
) -> DDLAnalysisResponse:
    """DDL 파일 파싱 → 스키마 추출 (G04).

    1. 샌드박스에서 .sql/.ddl 파일 필터링
    2. DDLParser로 파싱
    3. 테이블/FK 목록 반환
    """
    _validate_upload_id(upload_id)
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")

    try:
        sandbox_dir = _sandbox.get_sandbox_path(upload_id)
        if not sandbox_dir.exists():
            raise HTTPException(status_code=404, detail=f"업로드를 찾을 수 없습니다: {upload_id}")

        parser = DDLParser(dialect=dialect)
        all_tables: list[dict] = []
        all_errors: list[str] = []

        # DDL 파일 탐색
        ddl_extensions = {".sql", ".ddl"}
        ddl_files = [
            p for p in sandbox_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in ddl_extensions
        ]

        if not ddl_files:
            return DDLAnalysisResponse(
                upload_id=upload_id,
                tables_found=0,
                parse_errors=0,
                errors=["DDL 파일(.sql, .ddl)을 찾을 수 없습니다"],
            )

        for ddl_file in ddl_files:
            try:
                result = parser.parse_file(str(ddl_file))

                for table in result.tables:
                    all_tables.append({
                        "schema_name": table.schema_name,
                        "table_name": table.table_name,
                        "column_count": len(table.columns),
                        "pk_columns": table.primary_key.columns if table.primary_key else [],
                        "fk_count": len(table.foreign_keys),
                        "comment": table.comment or "",
                        "source_file": str(ddl_file.relative_to(sandbox_dir)),
                    })

                all_errors.extend(result.errors)

            except Exception as e:
                all_errors.append(f"{ddl_file.name}: {e}")

        logger.info(
            "DDL 분석 완료: upload_id=%s, tables=%d, errors=%d",
            upload_id, len(all_tables), len(all_errors),
        )

        return DDLAnalysisResponse(
            upload_id=upload_id,
            tables_found=len(all_tables),
            parse_errors=len(all_errors),
            tables=all_tables,
            errors=all_errors,
        )

    except HTTPException:
        raise
    except SandboxError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("DDL 분석 실패: %s", e)
        raise HTTPException(status_code=500, detail="DDL 분석 중 내부 오류 발생") from e


@router.delete("/{upload_id}")
async def cleanup_upload(
    upload_id: str,
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    """업로드 샌드박스 정리 — 분석 완료 후 호출"""
    _validate_upload_id(upload_id)
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")

    await _sandbox.cleanup(upload_id)
    return {"success": True, "message": f"샌드박스 정리 완료: {upload_id}"}


# ── Sprint 6: LLM 코드 분석 + Evidence ── #

@router.post("/{upload_id}/analyze")
async def analyze_source_code(
    upload_id: str,
    strategy: Literal["framework", "dbms", "auto"] = Query("auto"),
    target: str = Query("", description="대상 언어 (java/python/sql 등)"),
    user: CurrentUser = Depends(_get_current_user),
) -> StreamingResponse:
    """소스코드 분석 — NDJSON 스트리밍 (G01a).

    패턴 기반 로컬 추출 (JPA/SQLAlchemy/Django + DDL 파서).
    모든 결과에 AnalysisEvidence(판단 근거) 첨부.
    """
    _validate_upload_id(upload_id)
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")

    sandbox_dir = _sandbox.get_sandbox_path(upload_id)
    if not sandbox_dir.exists():
        raise HTTPException(status_code=404, detail=f"업로드를 찾을 수 없습니다: {upload_id}")

    async def _stream():
        # M2: 스트리밍 중 예외 발생 시 에러 이벤트 yield
        try:
            async for event in _analyzer.analyze(
                upload_id=upload_id,
                sandbox_dir=str(sandbox_dir),
                strategy=strategy,
                target=target,
            ):
                yield json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n"
        except Exception as exc:
            from app.models.evidence import AnalysisEvent
            error_event = AnalysisEvent(
                event_type="error",
                data={"message": f"분석 중 내부 오류: {str(exc)[:200]}"},
            )
            yield json.dumps(error_event.model_dump(mode="json"), ensure_ascii=False) + "\n"
            logger.exception("NDJSON stream error: upload_id=%s", upload_id)

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


@router.get("/{upload_id}/evidence")
async def list_evidence(
    upload_id: str,
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    """특정 업로드의 모든 분석 근거 조회 (G34)"""
    _validate_upload_id(upload_id)
    # M4: 역할 검증 추가
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")

    evidences = await evidence_store.get_by_upload(upload_id)
    return {
        "success": True,
        "data": [e.model_dump(mode="json") for e in evidences],
        "total": len(evidences),
    }


# ── Sprint 7: 코드 리니지 ── #

@router.post("/{upload_id}/lineage")
async def extract_code_lineage(
    upload_id: str,
    user: CurrentUser = Depends(_get_current_user),
) -> dict:
    """업로드된 SQL 코드에서 데이터 리니지 DAG 추출 (G13).

    source → transform → sink 흐름을 추출하고 Mermaid 다이어그램도 반환한다.
    """
    _validate_upload_id(upload_id)
    if user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="권한 부족")

    sandbox_dir = _sandbox.get_sandbox_path(upload_id)
    if not sandbox_dir.exists():
        raise HTTPException(status_code=404, detail=f"업로드를 찾을 수 없습니다: {upload_id}")

    try:
        graph = await _lineage_extractor.extract_lineage(upload_id, str(sandbox_dir))
        return {
            "success": True,
            "data": {
                "nodes": [n.model_dump(mode="json") for n in graph.nodes],
                "edges": [e.model_dump(mode="json") for e in graph.edges],
                "node_count": graph.node_count,
                "edge_count": graph.edge_count,
                "source_files": graph.source_files,
                "mermaid": graph.to_mermaid(),
                "errors": graph.errors,
            },
        }
    except Exception as e:
        logger.exception("리니지 추출 실패: %s", e)
        raise HTTPException(status_code=500, detail="리니지 추출 중 내부 오류 발생") from e
