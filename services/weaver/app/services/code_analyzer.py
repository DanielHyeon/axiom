"""G01a: LLM 기반 소스코드 분석 엔진 — 테이블/컬럼/FK 추출.

소스코드에서 데이터베이스 스키마 정보를 추출하는 MVP 분석기.
LLM(GPT-4o/Gemma-3)에게 코드를 보내 JSON 구조화 결과를 받는다.

분석 전략:
- framework: JPA/ORM 어노테이션 기반 추출 (Java/Python)
- dbms: SQL문/DDL 기반 추출
- auto: 파일 타입 감지 결과로 전략 자동 선택

모든 결과에 AnalysisEvidence(판단 근거)를 첨부한다.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, AsyncGenerator, Literal

from app.models.evidence import (
    AnalysisEvent,
    AnalysisEvidence,
    EvidenceType,
    evidence_store,
)
from app.models.provenance import ExtractionMethod
from app.services.evidence_redactor import evidence_redactor
from app.services.parsers.ddl_parser import DDLParser
from app.services.parsers.ddl_models import DDLParseResult
from app.services.parsers.ast_analyzer import python_ast_analyzer, java_block_analyzer, javalang_analyzer

logger = logging.getLogger("axiom.weaver.code_analyzer")

# 파일 읽기 최대 크기 (1MB)
_MAX_FILE_READ = 1024 * 1024

# LLM 청크 최대 길이 (토큰 제한 고려 — 약 4000자)
_MAX_CHUNK_CHARS = 4000


# ── JPA/ORM 패턴 기반 로컬 추출기 ── #

# JPA 어노테이션 패턴
_JPA_TABLE = re.compile(
    r'@Table\s*\(\s*name\s*=\s*["\'](\w+)["\']', re.IGNORECASE,
)
_JPA_ENTITY = re.compile(r'@Entity\b', re.IGNORECASE)
_JPA_COLUMN = re.compile(
    r'@Column\s*\([^)]*name\s*=\s*["\'](\w+)["\']', re.IGNORECASE,
)
_JPA_JOIN = re.compile(
    r'@JoinColumn\s*\([^)]*name\s*=\s*["\'](\w+)["\']', re.IGNORECASE,
)
_JPA_MANY_TO_ONE = re.compile(r'@ManyToOne\b', re.IGNORECASE)
_JPA_ONE_TO_MANY = re.compile(r'@OneToMany\b', re.IGNORECASE)

# SQLAlchemy 패턴
_SA_TABLE = re.compile(r'__tablename__\s*=\s*["\'](\w+)["\']')
_SA_COLUMN = re.compile(r'(\w+)\s*=\s*(?:db\.)?Column\s*\(')
_SA_FK = re.compile(r"ForeignKey\s*\(\s*['\"](\w+)\.(\w+)['\"]")

# Django Model 패턴
_DJ_FK = re.compile(r'(\w+)\s*=\s*models\.ForeignKey\s*\(\s*["\']?(\w+)')
_DJ_FIELD = re.compile(r'(\w+)\s*=\s*models\.(\w+Field)\s*\(')


class CodeAnalyzer:
    """LLM 기반 소스코드 분석 — 테이블/컬럼/FK 추출.

    Phase 1(MVP): 패턴 기반 로컬 추출 + DDL 파서 통합
    Phase 2(고도화): LLM API 호출로 복잡한 코드 분석 (Sprint 7-8)

    모든 결과에 AnalysisEvidence를 첨부하여 판단 근거를 기록한다.
    """

    def __init__(self) -> None:
        self._ddl_parser = DDLParser()

    async def analyze(
        self,
        upload_id: str,
        sandbox_dir: str,
        strategy: Literal["framework", "dbms", "auto"] = "auto",
        target: str = "",
    ) -> AsyncGenerator[AnalysisEvent, None]:
        """NDJSON 스트리밍 분석 — 단계별 이벤트 yield.

        Args:
            upload_id: 업로드 식별자
            sandbox_dir: 샌드박스 디렉토리 경로
            strategy: 분석 전략 (framework/dbms/auto)
            target: 대상 언어 (java/python/sql 등)
        """
        base = Path(sandbox_dir)
        if not base.exists():
            yield AnalysisEvent(event_type="error", data={"message": "샌드박스 미존재"})
            return

        # 1. 파일 수집 — M3: lazy 순회 + 파일 수 상한
        _MAX_SOURCE_FILES = 5000
        source_files = []
        for f in base.rglob("*"):
            if f.is_file() and f.suffix in _ANALYZABLE_EXTENSIONS:
                source_files.append(f)
                if len(source_files) >= _MAX_SOURCE_FILES:
                    logger.warning("파일 수 상한 도달: %d개, upload_id=%s", _MAX_SOURCE_FILES, upload_id)
                    break

        yield AnalysisEvent(
            event_type="progress",
            progress=0.05,
            data={"message": f"분석 대상 파일 {len(source_files)}개 발견", "total_files": len(source_files)},
        )

        if not source_files:
            yield AnalysisEvent(event_type="complete", progress=1.0, data={"tables": [], "fks": []})
            return

        # 2. 파일별 분석
        tables_found: list[dict] = []
        fks_found: list[dict] = []
        total = len(source_files)

        for i, file_path in enumerate(source_files):
            rel_path = str(file_path.relative_to(base))

            yield AnalysisEvent(
                event_type="file_detected",
                progress=0.1 + 0.7 * i / total,
                data={"file": rel_path},
            )

            try:
                ext = file_path.suffix.lower()
                content = file_path.read_text(encoding="utf-8", errors="ignore")[:_MAX_FILE_READ]

                # 전략별 분석 — G01b: AST 우선, 정규식 폴백
                if ext in (".sql", ".ddl"):
                    # DDL 파일 — 정적 파서 사용
                    async for event in self._analyze_ddl(upload_id, content, rel_path):
                        yield event
                        if event.event_type == "table_found":
                            tables_found.append(event.data)
                        elif event.event_type == "fk_inferred":
                            fks_found.append(event.data)

                elif ext == ".java":
                    # Java — G01b: javalang AST 우선 → 블록 파서 → 정규식 폴백
                    found_by_ast = False
                    # 1단계: javalang 정밀 파서 (설치 시)
                    if javalang_analyzer.is_available():
                        async for event in javalang_analyzer.analyze_file(content, rel_path, upload_id):
                            yield event
                            found_by_ast = True
                            if event.event_type == "table_found":
                                tables_found.append(event.data)
                            elif event.event_type == "fk_inferred":
                                fks_found.append(event.data)
                    # 2단계: 블록 파서 폴백
                    if not found_by_ast:
                        async for event in java_block_analyzer.analyze_file(content, rel_path, upload_id):
                            yield event
                            found_by_ast = True
                            if event.event_type == "table_found":
                                tables_found.append(event.data)
                            elif event.event_type == "fk_inferred":
                                fks_found.append(event.data)
                    # 3단계: 정규식 폴백
                    if not found_by_ast:
                        async for event in self._analyze_java(upload_id, content, rel_path):
                            yield event
                            if event.event_type == "table_found":
                                tables_found.append(event.data)
                            elif event.event_type == "fk_inferred":
                                fks_found.append(event.data)

                elif ext == ".py":
                    # Python — G01b: AST 우선 (정규식 폴백)
                    found_by_ast = False
                    async for event in python_ast_analyzer.analyze_file(content, rel_path, upload_id):
                        yield event
                        found_by_ast = True
                        if event.event_type == "table_found":
                            tables_found.append(event.data)
                        elif event.event_type == "fk_inferred":
                            fks_found.append(event.data)
                    if not found_by_ast:
                        async for event in self._analyze_python(upload_id, content, rel_path):
                            yield event
                            if event.event_type == "table_found":
                                tables_found.append(event.data)
                            elif event.event_type == "fk_inferred":
                                fks_found.append(event.data)

            except Exception as e:
                yield AnalysisEvent(
                    event_type="error",
                    progress=0.1 + 0.7 * (i + 1) / total,
                    data={"file": rel_path, "error": str(e)[:200]},
                )

        # 3. 완료
        yield AnalysisEvent(
            event_type="complete",
            progress=1.0,
            data={
                "tables_count": len(tables_found),
                "fks_count": len(fks_found),
                "tables": tables_found,
                "fks": fks_found,
            },
        )

    # ── DDL 분석 ── #

    async def _analyze_ddl(
        self,
        upload_id: str,
        content: str,
        rel_path: str,
    ) -> AsyncGenerator[AnalysisEvent, None]:
        """DDL 파일 — 정적 파서로 테이블/FK 추출"""
        result = self._ddl_parser.parse(content, source_file=rel_path)

        for table in result.tables:
            # Evidence 생성 (DDL 파서 결과)
            evidence = AnalysisEvidence(
                source_file=rel_path,
                line_start=0,
                line_end=0,
                code_snippet=f"CREATE TABLE {table.table_name} ({len(table.columns)} columns)",
                reasoning=f"DDL 정적 파서로 {table.table_name} 테이블 발견 (컬럼 {len(table.columns)}개, FK {len(table.foreign_keys)}개)",
                confidence=0.95,  # DDL 파서는 높은 신뢰도
                evidence_type=EvidenceType.DDL_PARSED,
            )
            evidence = evidence_redactor.redact_evidence(evidence)
            await evidence_store.save(upload_id, "table", table.table_name, evidence)

            yield AnalysisEvent(
                event_type="table_found",
                data={
                    "table_name": table.table_name,
                    "schema_name": table.schema_name,
                    "column_count": len(table.columns),
                    "source": "ddl_parser",
                },
                evidence=evidence,
            )

            for fk in table.foreign_keys:
                fk_evidence = AnalysisEvidence(
                    source_file=rel_path,
                    code_snippet=f"FOREIGN KEY ({', '.join(fk.source_columns)}) REFERENCES {fk.target_table}",
                    reasoning=f"DDL FK 제약조건: {table.table_name} → {fk.target_table}",
                    confidence=0.98,
                    evidence_type=EvidenceType.SQL_STATEMENT,
                )
                fk_evidence = evidence_redactor.redact_evidence(fk_evidence)
                await evidence_store.save(upload_id, "fk", f"{table.table_name}→{fk.target_table}", fk_evidence)

                yield AnalysisEvent(
                    event_type="fk_inferred",
                    data={
                        "source_table": table.table_name,
                        "source_columns": fk.source_columns,
                        "target_table": fk.target_table,
                        "target_columns": fk.target_columns,
                        "source": "ddl_parser",
                    },
                    evidence=fk_evidence,
                )

    # ── Java JPA 분석 ── #

    async def _analyze_java(
        self,
        upload_id: str,
        content: str,
        rel_path: str,
    ) -> AsyncGenerator[AnalysisEvent, None]:
        """Java 파일 — JPA 어노테이션 패턴 매칭"""
        # @Entity가 없으면 스킵
        if not _JPA_ENTITY.search(content):
            return

        # @Table(name="xxx") 추출
        table_match = _JPA_TABLE.search(content)
        if not table_match:
            return

        table_name = table_match.group(1)
        line_num = content[:table_match.start()].count("\n") + 1

        # 코드 조각 추출 (매치 주변 10줄)
        lines = content.split("\n")
        start = max(0, line_num - 3)
        end = min(len(lines), line_num + 10)
        snippet = "\n".join(lines[start:end])

        # 컬럼 추출
        columns = []
        for m in _JPA_COLUMN.finditer(content):
            columns.append(m.group(1))

        evidence = AnalysisEvidence(
            source_file=rel_path,
            line_start=line_num,
            line_end=line_num + 10,
            code_snippet=snippet[:500],
            reasoning=f"JPA @Entity + @Table(name='{table_name}') 어노테이션으로 테이블 매핑 확인. @Column {len(columns)}개 발견.",
            confidence=0.92,
            evidence_type=EvidenceType.ANNOTATION,
        )
        evidence = evidence_redactor.redact_evidence(evidence)
        await evidence_store.save(upload_id, "table", table_name, evidence)

        yield AnalysisEvent(
            event_type="table_found",
            data={
                "table_name": table_name,
                "column_count": len(columns),
                "columns": columns[:20],
                "source": "jpa_annotation",
            },
            evidence=evidence,
        )

        # FK 추출 — @ManyToOne + @JoinColumn
        for m in _JPA_JOIN.finditer(content):
            fk_col = m.group(1)
            fk_line = content[:m.start()].count("\n") + 1

            # @ManyToOne이 근처에 있는지 확인
            nearby = content[max(0, m.start() - 200):m.start()]
            if _JPA_MANY_TO_ONE.search(nearby):
                # 대상 테이블 추론 (컬럼명에서 _id 제거)
                target_table = fk_col.replace("_id", "").replace("Id", "") + "s"

                fk_evidence = AnalysisEvidence(
                    source_file=rel_path,
                    line_start=fk_line,
                    line_end=fk_line + 3,
                    code_snippet=lines[fk_line - 1][:200] if fk_line <= len(lines) else "",
                    reasoning=f"@ManyToOne + @JoinColumn(name='{fk_col}')로 FK 관계 추론. 대상 테이블: {target_table} (이름 패턴 기반 — 검증 필요)",
                    confidence=0.55,  # N2: 이름 패턴 추론은 낮은 신뢰도
                    evidence_type=EvidenceType.NAMING_CONVENTION,
                )
                fk_evidence = evidence_redactor.redact_evidence(fk_evidence)
                await evidence_store.save(upload_id, "fk", f"{table_name}→{target_table}", fk_evidence)

                yield AnalysisEvent(
                    event_type="fk_inferred",
                    data={
                        "source_table": table_name,
                        "source_columns": [fk_col],
                        "target_table": target_table,
                        "source": "jpa_annotation",
                    },
                    evidence=fk_evidence,
                )

    # ── Python ORM 분석 ── #

    async def _analyze_python(
        self,
        upload_id: str,
        content: str,
        rel_path: str,
    ) -> AsyncGenerator[AnalysisEvent, None]:
        """Python 파일 — SQLAlchemy/Django 패턴 매칭"""

        # SQLAlchemy __tablename__ 추출
        sa_match = _SA_TABLE.search(content)
        if sa_match:
            table_name = sa_match.group(1)
            line_num = content[:sa_match.start()].count("\n") + 1

            # Column 추출
            columns = [m.group(1) for m in _SA_COLUMN.finditer(content)]

            lines = content.split("\n")
            start = max(0, line_num - 2)
            end = min(len(lines), line_num + 8)
            snippet = "\n".join(lines[start:end])

            evidence = AnalysisEvidence(
                source_file=rel_path,
                line_start=line_num,
                line_end=min(line_num + 10, len(lines)),
                code_snippet=snippet[:500],
                reasoning=f"SQLAlchemy __tablename__ = '{table_name}' 정의 확인. Column {len(columns)}개 발견.",
                confidence=0.90,
                evidence_type=EvidenceType.ORM_DEFINITION,
            )
            evidence = evidence_redactor.redact_evidence(evidence)
            await evidence_store.save(upload_id, "table", table_name, evidence)

            yield AnalysisEvent(
                event_type="table_found",
                data={"table_name": table_name, "column_count": len(columns), "source": "sqlalchemy"},
                evidence=evidence,
            )

            # SQLAlchemy ForeignKey 추출
            for fk_m in _SA_FK.finditer(content):
                target_table = fk_m.group(1)
                target_col = fk_m.group(2)
                fk_line = content[:fk_m.start()].count("\n") + 1

                fk_evidence = AnalysisEvidence(
                    source_file=rel_path,
                    line_start=fk_line,
                    line_end=fk_line + 1,
                    code_snippet=content.split("\n")[fk_line - 1][:200] if fk_line <= len(lines) else "",
                    reasoning=f"SQLAlchemy ForeignKey('{target_table}.{target_col}') 정의 확인.",
                    confidence=0.93,
                    evidence_type=EvidenceType.ORM_DEFINITION,
                )
                fk_evidence = evidence_redactor.redact_evidence(fk_evidence)
                await evidence_store.save(upload_id, "fk", f"{table_name}→{target_table}", fk_evidence)

                yield AnalysisEvent(
                    event_type="fk_inferred",
                    data={"source_table": table_name, "target_table": target_table,
                          "target_column": target_col, "source": "sqlalchemy"},
                    evidence=fk_evidence,
                )
            return  # SQLAlchemy 발견 시 Django 분석 스킵

        # Django ForeignKey 추출
        for dj_m in _DJ_FK.finditer(content):
            field_name = dj_m.group(1)
            target_model = dj_m.group(2)
            dj_line = content[:dj_m.start()].count("\n") + 1
            lines = content.split("\n")

            fk_evidence = AnalysisEvidence(
                source_file=rel_path,
                line_start=dj_line,
                line_end=dj_line + 1,
                code_snippet=lines[dj_line - 1][:200] if dj_line <= len(lines) else "",
                reasoning=f"Django models.ForeignKey('{target_model}') 정의. 필드명: {field_name}",
                confidence=0.90,
                evidence_type=EvidenceType.ORM_DEFINITION,
            )
            fk_evidence = evidence_redactor.redact_evidence(fk_evidence)

            # Django에서는 모델 이름에서 테이블 이름 추론 (app_label 없이 소문자 복수형)
            inferred_target = target_model.lower() + "s"
            await evidence_store.save(upload_id, "fk", f"→{inferred_target}", fk_evidence)

            yield AnalysisEvent(
                event_type="fk_inferred",
                data={"field_name": field_name, "target_model": target_model,
                      "inferred_table": inferred_target, "source": "django"},
                evidence=fk_evidence,
            )


# 분석 가능 확장자
_ANALYZABLE_EXTENSIONS = {
    ".java", ".py", ".sql", ".ddl",
    ".kt", ".scala", ".groovy",  # JVM 계열 (Phase 2 확장)
}
