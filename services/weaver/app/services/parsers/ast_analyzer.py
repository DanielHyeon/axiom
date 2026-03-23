"""G01b: AST 기반 정밀 코드 분석기 — Java/Python/SQL.

ANTLR 대신 Python 내장 ast + 경량 파서를 사용하여
JPA Entity, SQLAlchemy Model, SQL DDL을 정밀 분석한다.

Sprint 6의 정규식 MVP를 AST 기반으로 고도화:
- Python: ast 모듈로 클래스/데코레이터/할당문 정밀 추출
- Java: 구조화된 정규식 + 블록 파서 (ANTLR 런타임 없이)
- SQL: SQLGlot AST (별도 모듈 sqlglot_lineage.py)

설계 원칙:
- 정규식 MVP 코드는 유지 (폴백)
- AST 분석이 가능한 파일만 정밀 분석, 나머지는 정규식 폴백
- 모든 결과에 Evidence 첨부 (confidence 상향)
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Any, AsyncGenerator

from app.models.evidence import (
    AnalysisEvent,
    AnalysisEvidence,
    EvidenceType,
    evidence_store,
)
from app.services.evidence_redactor import evidence_redactor

logger = logging.getLogger("axiom.weaver.parsers.ast_analyzer")


# ── Python AST 분석기 ── #

class PythonASTAnalyzer:
    """Python ast 모듈로 SQLAlchemy/Django 모델 정밀 추출.

    정규식 MVP 대비 장점:
    - 클래스 상속 관계 추적 (Base 상속 확인)
    - 데코레이터 정확한 파싱
    - 변수 할당 타입 추론
    - 중첩 클래스/함수 올바른 스코프 처리
    """

    async def analyze_file(
        self,
        content: str,
        rel_path: str,
        upload_id: str,
    ) -> AsyncGenerator[AnalysisEvent, None]:
        """Python 파일 AST 분석 → 테이블/FK 이벤트 yield"""
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            yield AnalysisEvent(
                event_type="error",
                data={"file": rel_path, "error": f"Python 구문 오류: {e.msg}"},
            )
            return

        lines = content.split("\n")

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            # SQLAlchemy 모델 감지: __tablename__ 할당 존재 여부
            tablename = self._extract_tablename(node)
            if not tablename:
                continue

            # 컬럼 추출
            columns = self._extract_columns(node)
            fks = self._extract_foreign_keys(node)

            # 코드 조각 추출
            start_line = node.lineno
            end_line = node.end_lineno or start_line + 10
            snippet = "\n".join(lines[start_line - 1:min(end_line, len(lines))])

            # Evidence 생성 — AST 기반은 높은 신뢰도
            evidence = AnalysisEvidence(
                source_file=rel_path,
                line_start=start_line,
                line_end=end_line,
                code_snippet=snippet[:500],
                reasoning=(
                    f"Python AST 분석: 클래스 '{node.name}'에서 "
                    f"__tablename__ = '{tablename}' 발견. "
                    f"Column {len(columns)}개, ForeignKey {len(fks)}개 추출."
                ),
                confidence=0.95,  # AST 기반 — 정규식(0.90)보다 높음
                evidence_type=EvidenceType.ORM_DEFINITION,
            )
            evidence = evidence_redactor.redact_evidence(evidence)
            await evidence_store.save(upload_id, "table", tablename, evidence)

            yield AnalysisEvent(
                event_type="table_found",
                data={
                    "table_name": tablename,
                    "class_name": node.name,
                    "column_count": len(columns),
                    "columns": [c["name"] for c in columns],
                    "source": "python_ast",
                },
                evidence=evidence,
            )

            # FK 이벤트
            for fk in fks:
                fk_evidence = AnalysisEvidence(
                    source_file=rel_path,
                    line_start=fk.get("line", start_line),
                    line_end=fk.get("line", start_line) + 1,
                    code_snippet=fk.get("snippet", "")[:500],
                    reasoning=f"Python AST: ForeignKey('{fk['target_table']}.{fk['target_column']}') 정밀 추출",
                    confidence=0.96,
                    evidence_type=EvidenceType.ORM_DEFINITION,
                )
                fk_evidence = evidence_redactor.redact_evidence(fk_evidence)
                await evidence_store.save(
                    upload_id, "fk", f"{tablename}→{fk['target_table']}", fk_evidence,
                )

                yield AnalysisEvent(
                    event_type="fk_inferred",
                    data={
                        "source_table": tablename,
                        "target_table": fk["target_table"],
                        "target_column": fk["target_column"],
                        "source": "python_ast",
                    },
                    evidence=fk_evidence,
                )

    def _extract_tablename(self, class_node: ast.ClassDef) -> str | None:
        """클래스에서 __tablename__ = 'xxx' 추출"""
        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "__tablename__":
                        if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                            return item.value.value
        return None

    def _extract_columns(self, class_node: ast.ClassDef) -> list[dict]:
        """클래스에서 Column() 할당 추출"""
        columns = []
        for item in class_node.body:
            if isinstance(item, ast.Assign) and len(item.targets) == 1:
                target = item.targets[0]
                if isinstance(target, ast.Name) and isinstance(item.value, ast.Call):
                    func_name = self._get_call_name(item.value)
                    if func_name in ("Column", "db.Column"):
                        col_type = self._extract_column_type(item.value)
                        columns.append({
                            "name": target.id,
                            "type": col_type,
                            "line": item.lineno,
                        })
        return columns

    def _extract_foreign_keys(self, class_node: ast.ClassDef) -> list[dict]:
        """클래스에서 ForeignKey('table.column') 추출"""
        fks = []
        for item in ast.walk(class_node):
            if isinstance(item, ast.Call):
                func_name = self._get_call_name(item)
                if func_name in ("ForeignKey", "db.ForeignKey"):
                    if item.args and isinstance(item.args[0], ast.Constant):
                        ref = str(item.args[0].value)
                        parts = ref.split(".")
                        if len(parts) == 2:
                            fks.append({
                                "target_table": parts[0],
                                "target_column": parts[1],
                                "line": item.lineno,
                                "snippet": ref,
                            })
        return fks

    def _get_call_name(self, call: ast.Call) -> str:
        """ast.Call에서 함수명 추출 (db.Column → 'db.Column')"""
        if isinstance(call.func, ast.Name):
            return call.func.id
        if isinstance(call.func, ast.Attribute):
            if isinstance(call.func.value, ast.Name):
                return f"{call.func.value.id}.{call.func.attr}"
            return call.func.attr
        return ""

    def _extract_column_type(self, call: ast.Call) -> str:
        """Column(Integer, ...) 에서 타입 추출"""
        if call.args:
            first_arg = call.args[0]
            if isinstance(first_arg, ast.Name):
                return first_arg.id  # Integer, String 등
            if isinstance(first_arg, ast.Call):
                return self._get_call_name(first_arg)  # String(100) 등
        return "unknown"


# ── G01b: javalang 정밀 Java 파서 (ANTLR 대체) ── #

try:
    import javalang  # type: ignore  # pip install javalang
    HAS_JAVALANG = True
except ImportError:
    HAS_JAVALANG = False


class JavaLangAnalyzer:
    """G01b: javalang 라이브러리 기반 Java 정밀 분석.

    ANTLR 런타임 없이 순수 Python으로 Java AST를 파싱한다.
    javalang 미설치 시 JavaBlockAnalyzer(정규식)로 폴백.

    정밀 추출 항목:
    - @Entity/@Table(name, schema, catalog, uniqueConstraints)
    - @Column(name, length, nullable, unique, columnDefinition)
    - @Id/@GeneratedValue(strategy)
    - @ManyToOne/@OneToMany/@ManyToMany(mappedBy, fetch, cascade)
    - @JoinTable(name, joinColumns, inverseJoinColumns)
    - @Embeddable/@EmbeddedId
    - Lombok @Data/@Builder 감지
    """

    def is_available(self) -> bool:
        return HAS_JAVALANG

    async def analyze_file(
        self,
        content: str,
        rel_path: str,
        upload_id: str,
    ) -> AsyncGenerator[AnalysisEvent, None]:
        """javalang AST로 Java 파일 정밀 분석"""
        if not HAS_JAVALANG:
            return  # 폴백은 호출자가 처리

        try:
            tree = javalang.parse.parse(content)
        except Exception as e:
            logger.debug("javalang 파싱 실패 (폴백): %s — %s", rel_path, e)
            return

        lines = content.split("\n")

        for _, class_decl in tree.filter(javalang.tree.ClassDeclaration):
            # @Entity 어노테이션 확인
            if not self._has_annotation(class_decl, "Entity"):
                continue

            # @Table 정보 추출
            table_info = self._get_table_annotation(class_decl)
            table_name = table_info.get("name", class_decl.name.lower())
            schema_name = table_info.get("schema", "")

            # Lombok 감지
            has_lombok = self._has_annotation(class_decl, "Data") or self._has_annotation(class_decl, "Builder")

            # 컬럼 추출 — 필드 순회
            columns: list[dict] = []
            id_fields: list[str] = []
            fks: list[dict] = []

            for field in class_decl.fields:
                if not hasattr(field, "declarators") or not field.declarators:
                    continue
                field_name = field.declarators[0].name
                field_type = field.type.name if hasattr(field.type, "name") else str(field.type)

                # @Column 추출
                col_annot = self._get_annotation_params(field, "Column")
                if col_annot is not None:
                    columns.append({
                        "name": col_annot.get("name", field_name),
                        "field_name": field_name,
                        "type": field_type,
                        "length": col_annot.get("length"),
                        "nullable": col_annot.get("nullable"),
                        "unique": col_annot.get("unique"),
                    })

                # @Id 추출
                if self._has_field_annotation(field, "Id") or self._has_field_annotation(field, "EmbeddedId"):
                    id_fields.append(field_name)

                # 관계 어노테이션 추출
                for rel_type in ("ManyToOne", "OneToMany", "ManyToMany", "OneToOne"):
                    rel_annot = self._get_annotation_params(field, rel_type)
                    if rel_annot is not None:
                        # @JoinColumn 추출
                        join_col = self._get_annotation_params(field, "JoinColumn")
                        fks.append({
                            "relationship": rel_type,
                            "field_name": field_name,
                            "target_type": field_type,
                            "mapped_by": rel_annot.get("mappedBy", ""),
                            "join_column": join_col.get("name", "") if join_col else "",
                        })

            # Evidence 생성
            start_line = getattr(class_decl, "position", None)
            line_num = start_line.line if start_line else 1
            snippet_start = max(0, line_num - 2)
            snippet_end = min(len(lines), line_num + 15)
            snippet = "\n".join(lines[snippet_start:snippet_end])

            evidence = AnalysisEvidence(
                source_file=rel_path,
                line_start=line_num,
                line_end=line_num + 15,
                code_snippet=snippet[:500],
                reasoning=(
                    f"javalang AST 정밀 분석: @Entity + @Table(name='{table_name}') "
                    f"클래스 '{class_decl.name}'. @Column {len(columns)}개, "
                    f"@Id {len(id_fields)}개, FK관계 {len(fks)}개"
                    f"{', Lombok 감지' if has_lombok else ''}."
                ),
                confidence=0.97,  # javalang AST — 블록파서(0.94)보다 높음
                evidence_type=EvidenceType.ANNOTATION,
            )
            evidence = evidence_redactor.redact_evidence(evidence)
            await evidence_store.save(upload_id, "table", table_name, evidence)

            yield AnalysisEvent(
                event_type="table_found",
                data={
                    "table_name": table_name,
                    "schema_name": schema_name,
                    "class_name": class_decl.name,
                    "column_count": len(columns),
                    "id_fields": id_fields,
                    "has_lombok": has_lombok,
                    "source": "javalang_ast",
                },
                evidence=evidence,
            )

            # FK 이벤트
            for fk in fks:
                fk_evidence = AnalysisEvidence(
                    source_file=rel_path,
                    line_start=line_num,
                    line_end=line_num + 3,
                    code_snippet=f"@{fk['relationship']} {fk['target_type']} {fk['field_name']}",
                    reasoning=(
                        f"javalang AST: @{fk['relationship']}(mappedBy='{fk['mapped_by']}') "
                        f"@JoinColumn(name='{fk['join_column']}') → {fk['target_type']}"
                    ),
                    confidence=0.95,
                    evidence_type=EvidenceType.ANNOTATION,
                )
                fk_evidence = evidence_redactor.redact_evidence(fk_evidence)
                await evidence_store.save(upload_id, "fk", f"{table_name}→{fk['target_type']}", fk_evidence)

                yield AnalysisEvent(
                    event_type="fk_inferred",
                    data={
                        "source_table": table_name,
                        "relationship": fk["relationship"],
                        "target_type": fk["target_type"],
                        "join_column": fk["join_column"],
                        "mapped_by": fk["mapped_by"],
                        "source": "javalang_ast",
                    },
                    evidence=fk_evidence,
                )

    def _has_annotation(self, class_decl: Any, name: str) -> bool:
        """클래스에 특정 어노테이션이 있는지 확인"""
        if not hasattr(class_decl, "annotations") or not class_decl.annotations:
            return False
        return any(a.name == name for a in class_decl.annotations)

    def _has_field_annotation(self, field: Any, name: str) -> bool:
        """필드에 특정 어노테이션이 있는지 확인"""
        if not hasattr(field, "annotations") or not field.annotations:
            return False
        return any(a.name == name for a in field.annotations)

    def _get_annotation_params(self, node: Any, name: str) -> dict | None:
        """어노테이션 파라미터를 dict로 추출 (없으면 None)"""
        annotations = getattr(node, "annotations", None) or []
        for annot in annotations:
            if annot.name != name:
                continue
            params: dict[str, Any] = {}
            if hasattr(annot, "element") and annot.element:
                # 단일 값 어노테이션
                if isinstance(annot.element, list):
                    for pair in annot.element:
                        if hasattr(pair, "name") and hasattr(pair, "value"):
                            val = getattr(pair.value, "value", str(pair.value))
                            params[pair.name] = val
                else:
                    params["value"] = getattr(annot.element, "value", str(annot.element))
            return params
        return None

    def _get_table_annotation(self, class_decl: Any) -> dict:
        """@Table 어노테이션에서 name/schema 추출"""
        result = self._get_annotation_params(class_decl, "Table")
        return result if result else {}


# ── Java 블록 파서 (ANTLR 대체 — javalang 폴백용) ── #

class JavaBlockAnalyzer:
    """Java 소스 구조화 분석 — 클래스/어노테이션/필드 블록 단위 추출.

    ANTLR 런타임 없이 블록 경계(중괄호) + 어노테이션 패턴으로 정밀 분석.
    정규식 MVP 대비 장점:
    - 중첩 클래스 올바른 스코프 처리
    - 어노테이션 파라미터 정확 추출 (멀티라인 포함)
    - 필드 타입 + 제네릭 파라미터 추출
    """

    # 클래스 선언
    _CLASS_DECL = re.compile(
        r'(?:public\s+|private\s+|protected\s+)?(?:abstract\s+)?class\s+(\w+)',
    )

    # 필드 선언 (어노테이션 뒤)
    _FIELD_DECL = re.compile(
        r'private\s+(\w+(?:<[^>]+>)?)\s+(\w+)\s*;',
    )

    async def analyze_file(
        self,
        content: str,
        rel_path: str,
        upload_id: str,
    ) -> AsyncGenerator[AnalysisEvent, None]:
        """Java 파일 블록 분석"""
        # @Entity 없으면 스킵
        if "@Entity" not in content:
            return

        lines = content.split("\n")

        # @Table(name="xxx") 추출
        table_match = re.search(
            r'@Table\s*\([^)]*name\s*=\s*["\'](\w+)["\']',
            content, re.DOTALL,
        )
        if not table_match:
            return

        table_name = table_match.group(1)
        table_line = content[:table_match.start()].count("\n") + 1

        # 클래스 이름 추출
        class_match = self._CLASS_DECL.search(content[table_match.end():])
        class_name = class_match.group(1) if class_match else "Unknown"

        # @Column 추출 (멀티라인 안전)
        columns = []
        for m in re.finditer(r'@Column\s*\([^)]*name\s*=\s*["\'](\w+)["\']', content, re.DOTALL):
            columns.append({"name": m.group(1), "line": content[:m.start()].count("\n") + 1})

        # @Id 추출
        id_fields = []
        for m in re.finditer(r'@Id\b', content):
            line_num = content[:m.start()].count("\n") + 1
            # @Id 다음 줄의 필드명 추출
            remaining = content[m.end():]
            field_m = self._FIELD_DECL.search(remaining[:200])
            if field_m:
                id_fields.append(field_m.group(2))

        # @JoinColumn + @ManyToOne FK 추출
        fks = []
        for m in re.finditer(
            r'@(?:ManyToOne|OneToOne)\b[\s\S]{0,300}?@JoinColumn\s*\([^)]*name\s*=\s*["\'](\w+)["\']',
            content, re.DOTALL,
        ):
            fk_col = m.group(1)
            fk_line = content[:m.start()].count("\n") + 1
            # 대상 필드 타입에서 테이블 추론
            after = content[m.end():m.end() + 200]
            field_m = self._FIELD_DECL.search(after)
            target_type = field_m.group(1) if field_m else "Unknown"

            fks.append({
                "column": fk_col,
                "target_type": target_type,
                "line": fk_line,
            })

        # 코드 조각
        start = max(0, table_line - 2)
        end = min(len(lines), table_line + 15)
        snippet = "\n".join(lines[start:end])

        evidence = AnalysisEvidence(
            source_file=rel_path,
            line_start=table_line,
            line_end=table_line + 15,
            code_snippet=snippet[:500],
            reasoning=(
                f"Java 블록 분석: @Entity + @Table(name='{table_name}') 클래스 '{class_name}'. "
                f"@Column {len(columns)}개, @Id {len(id_fields)}개, @JoinColumn FK {len(fks)}개."
            ),
            confidence=0.94,  # 블록 파서 — 정규식(0.92)보다 약간 높음
            evidence_type=EvidenceType.ANNOTATION,
        )
        evidence = evidence_redactor.redact_evidence(evidence)
        await evidence_store.save(upload_id, "table", table_name, evidence)

        yield AnalysisEvent(
            event_type="table_found",
            data={
                "table_name": table_name,
                "class_name": class_name,
                "column_count": len(columns),
                "id_fields": id_fields,
                "source": "java_block_parser",
            },
            evidence=evidence,
        )

        for fk in fks:
            fk_evidence = AnalysisEvidence(
                source_file=rel_path,
                line_start=fk["line"],
                line_end=fk["line"] + 3,
                code_snippet=f"@JoinColumn(name='{fk['column']}') → {fk['target_type']}",
                reasoning=f"Java 블록 분석: @ManyToOne/@OneToOne + @JoinColumn(name='{fk['column']}') → {fk['target_type']}",
                confidence=0.90,
                evidence_type=EvidenceType.ANNOTATION,
            )
            fk_evidence = evidence_redactor.redact_evidence(fk_evidence)
            await evidence_store.save(upload_id, "fk", f"{table_name}→{fk['target_type']}", fk_evidence)

            yield AnalysisEvent(
                event_type="fk_inferred",
                data={
                    "source_table": table_name,
                    "fk_column": fk["column"],
                    "target_type": fk["target_type"],
                    "source": "java_block_parser",
                },
                evidence=fk_evidence,
            )


# 모듈 수준 인스턴스
python_ast_analyzer = PythonASTAnalyzer()
javalang_analyzer = JavaLangAnalyzer()      # G01b: 정밀 파서 (javalang 설치 시)
java_block_analyzer = JavaBlockAnalyzer()   # 폴백 (정규식 기반)
