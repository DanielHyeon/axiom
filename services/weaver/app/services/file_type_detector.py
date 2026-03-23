"""G25: 파일 타입 자동 감지 — 언어/프레임워크 추정.

업로드된 파일에서 확장자 + 내용 패턴 기반으로 언어와 프레임워크를 추정한다.
3단계: 확장자 1차 → 내용 패턴 2차 → (Phase 3) LLM 3차
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.services.upload_sandbox import SandboxFileInfo

logger = logging.getLogger("axiom.weaver.file_type_detector")


# ── 모델 ── #

class FileTypeInfo(BaseModel):
    """개별 파일 타입 정보"""
    relative_path: str
    language: str = "unknown"             # java, python, sql, kotlin 등
    framework: str | None = None          # spring, django, sqlalchemy 등
    category: str = "source"              # source, config, data, ddl, doc


class FileTypeDetectionResult(BaseModel):
    """파일 타입 감지 결과"""
    upload_id: str
    files: list[FileTypeInfo] = Field(default_factory=list)
    by_language: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    suggested_strategy: str = "auto"      # auto, ddl_only, code_analysis, mixed
    suggested_target: str = ""            # 주요 언어/프레임워크


# ── 확장자 → 언어 매핑 ── #

_EXT_TO_LANGUAGE: dict[str, str] = {
    ".java": "java", ".kt": "kotlin", ".scala": "scala", ".groovy": "groovy",
    ".py": "python", ".pyx": "python",
    ".js": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".rb": "ruby", ".go": "go", ".rs": "rust",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp", ".cs": "csharp",
    ".sql": "sql", ".ddl": "sql",
    ".xml": "xml", ".json": "json", ".yml": "yaml", ".yaml": "yaml",
    ".properties": "config", ".cfg": "config", ".ini": "config",
    ".gradle": "gradle", ".pom": "xml",
    ".md": "markdown", ".txt": "text",
    ".csv": "data",
    ".sh": "shell",
}

_EXT_TO_CATEGORY: dict[str, str] = {
    ".sql": "ddl", ".ddl": "ddl",
    ".xml": "config", ".json": "config", ".yml": "config", ".yaml": "config",
    ".properties": "config", ".cfg": "config", ".ini": "config",
    ".gradle": "config", ".pom": "config",
    ".md": "doc", ".txt": "doc",
    ".csv": "data",
}


# ── 내용 기반 프레임워크 감지 패턴 ── #

_FRAMEWORK_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # Java 프레임워크
    ("java", re.compile(r"@(Entity|Table|Column|Id|ManyToOne|OneToMany)", re.MULTILINE), "jpa"),
    ("java", re.compile(r"@(SpringBootApplication|RestController|Service|Repository)", re.MULTILINE), "spring"),
    ("java", re.compile(r"import\s+org\.mybatis", re.MULTILINE), "mybatis"),
    ("java", re.compile(r"import\s+org\.hibernate", re.MULTILINE), "hibernate"),
    # Python 프레임워크
    ("python", re.compile(r"from\s+(django|rest_framework)", re.MULTILINE), "django"),
    ("python", re.compile(r"from\s+(fastapi|starlette)", re.MULTILINE), "fastapi"),
    ("python", re.compile(r"from\s+sqlalchemy", re.MULTILINE), "sqlalchemy"),
    ("python", re.compile(r"from\s+flask", re.MULTILINE), "flask"),
    # SQL 방언
    ("sql", re.compile(r"CREATE\s+TABLE", re.IGNORECASE | re.MULTILINE), "ddl"),
    ("sql", re.compile(r"CREATE\s+OR\s+REPLACE\s+FUNCTION", re.IGNORECASE), "plpgsql"),
    ("sql", re.compile(r"CREATE\s+PROCEDURE", re.IGNORECASE), "stored_proc"),
    # TypeScript/JavaScript
    ("typescript", re.compile(r"from\s+['\"]@nestjs/", re.MULTILINE), "nestjs"),
    ("typescript", re.compile(r"from\s+['\"]express", re.MULTILINE), "express"),
    ("typescript", re.compile(r"from\s+['\"]typeorm", re.MULTILINE), "typeorm"),
]


# ── 서비스 ── #

class FileTypeDetector:
    """파일 타입 + 프레임워크 자동 감지.

    사용법:
        detector = FileTypeDetector()
        result = detector.detect(upload_id, sandbox_files, sandbox_dir)
    """

    def detect(
        self,
        upload_id: str,
        files: list[SandboxFileInfo],
        sandbox_dir: str,
    ) -> FileTypeDetectionResult:
        """파일 목록에서 언어/프레임워크 감지"""
        file_infos: list[FileTypeInfo] = []
        lang_counter: Counter = Counter()
        cat_counter: Counter = Counter()

        for f in files:
            ext = f.extension.lower()

            # 1차: 확장자 기반 언어 분류
            language = _EXT_TO_LANGUAGE.get(ext, "unknown")
            category = _EXT_TO_CATEGORY.get(ext, "source")
            framework = None

            # 2차: 내용 기반 프레임워크 감지 (소스 파일만)
            if category == "source" and language not in ("unknown", "shell"):
                framework = self._detect_framework(
                    language, Path(sandbox_dir) / f.relative_path,
                )

            info = FileTypeInfo(
                relative_path=f.relative_path,
                language=language,
                framework=framework,
                category=category,
            )
            file_infos.append(info)
            lang_counter[language] += 1
            cat_counter[category] += 1

        # 전략 추천
        suggested_strategy = self._suggest_strategy(lang_counter, cat_counter)
        suggested_target = self._suggest_target(lang_counter, file_infos)

        return FileTypeDetectionResult(
            upload_id=upload_id,
            files=file_infos,
            by_language=dict(lang_counter),
            by_category=dict(cat_counter),
            suggested_strategy=suggested_strategy,
            suggested_target=suggested_target,
        )

    def _detect_framework(self, language: str, file_path: Path) -> str | None:
        """파일 내용에서 프레임워크 키워드 감지"""
        try:
            if not file_path.exists() or file_path.stat().st_size > 1024 * 1024:
                return None  # 1MB 초과 파일은 스킵

            content = file_path.read_text(encoding="utf-8", errors="ignore")[:8192]

            for lang, pattern, fw_name in _FRAMEWORK_PATTERNS:
                if lang == language and pattern.search(content):
                    return fw_name

        except Exception:
            pass
        return None

    def _suggest_strategy(
        self,
        lang_counter: Counter,
        cat_counter: Counter,
    ) -> str:
        """분석 전략 추천"""
        ddl_count = cat_counter.get("ddl", 0)
        source_count = cat_counter.get("source", 0)
        total = sum(cat_counter.values())

        if total == 0:
            return "auto"

        # DDL 파일만 있는 경우
        if ddl_count > 0 and source_count == 0:
            return "ddl_only"

        # 소스 파일만 있는 경우
        if source_count > 0 and ddl_count == 0:
            return "code_analysis"

        # 둘 다 있으면 mixed
        if ddl_count > 0 and source_count > 0:
            return "mixed"

        return "auto"

    def _suggest_target(
        self,
        lang_counter: Counter,
        file_infos: list[FileTypeInfo],
    ) -> str:
        """주요 언어/프레임워크 추천"""
        # 가장 많은 소스 언어
        source_langs = {k: v for k, v in lang_counter.items()
                        if k not in ("unknown", "config", "data", "markdown", "text")}
        if not source_langs:
            return ""

        top_lang = max(source_langs, key=lambda k: source_langs[k])

        # 프레임워크가 감지된 경우 추가
        frameworks = [f.framework for f in file_infos if f.framework and f.language == top_lang]
        if frameworks:
            top_fw = Counter(frameworks).most_common(1)[0][0]
            return f"{top_lang}/{top_fw}"

        return top_lang
