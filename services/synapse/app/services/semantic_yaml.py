"""
Metrics as Code — YAML 기반 시멘틱 계약 직렬화/역직렬화

P3 §5.4: 시멘틱 계약을 YAML 파일로 내보내고(export),
YAML 파일에서 가져오는(import) 단방향 파이프라인.
Git PR 기반 승인 워크플로의 첫 단계이다.

핵심 설계:
- Export: SemanticStore에서 읽어 YAML 문자열 생성
- Import: YAML 파싱 → 검증 → SemanticStore upsert
- Validation: 구조 검증 + SQL fragment 안전성 검사
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog
import yaml

from app.services.semantic_store import SemanticStore, _validate_sql_fragment

logger = structlog.get_logger()

# 현재 지원하는 YAML 스키마 버전
_SUPPORTED_VERSIONS = {"1.0"}

# 객체 타입별 필수 필드 정의 (import 시 검증용)
_REQUIRED_FIELDS: dict[str, set[str]] = {
    "concepts": {"concept_id", "name_ko"},
    "entities": {"entity_id", "physical_source_ref"},
    "measures": {"measure_id", "entity_id", "name", "sql_expression"},
    "dimensions": {"dimension_id", "entity_id", "name", "sql_expression"},
    "joins": {"join_id", "left_entity_id", "right_entity_id", "join_condition"},
    "grains": {"grain_id", "entity_id", "grain_key_set"},
    "quality_contracts": {"quality_contract_id", "target_type", "target_id"},
    "context_packs": {"context_pack_id", "intent_type"},
}

# SQL fragment 가 포함될 수 있는 필드 목록 (안전성 검증 대상)
_SQL_FIELDS: dict[str, list[str]] = {
    "measures": ["sql_expression", "filter_expression"],
    "dimensions": ["sql_expression"],
    "joins": ["join_condition"],
    "grains": ["uniqueness_test"],
}


class SemanticYamlValidator:
    """YAML 구조와 내용을 검증한다.

    import 전에 호출하여, 유효하지 않은 데이터가 DB에 들어가는 것을 방지한다.
    """

    def validate(self, parsed: dict[str, Any]) -> list[str]:
        """파싱된 YAML dict를 검증하고, 오류 메시지 목록을 반환한다.

        빈 리스트이면 검증 통과.
        """
        errors: list[str] = []

        # 1) 버전 확인
        version = parsed.get("axiom_semantic_version")
        if not version:
            errors.append("axiom_semantic_version 필드가 필요합니다")
        elif str(version) not in _SUPPORTED_VERSIONS:
            errors.append(
                f"지원하지 않는 axiom_semantic_version: {version} "
                f"(지원: {_SUPPORTED_VERSIONS})"
            )

        # 2) 각 섹션별 필수 필드 검증
        for section, required in _REQUIRED_FIELDS.items():
            items = parsed.get(section, [])
            if not isinstance(items, list):
                if items is not None:
                    errors.append(f"'{section}'은 리스트여야 합니다")
                continue
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(f"{section}[{idx}]가 딕셔너리가 아닙니다")
                    continue
                for field in required:
                    if field not in item or item[field] is None:
                        errors.append(f"{section}[{idx}]: 필수 필드 '{field}'가 누락되었습니다")

        # 3) SQL fragment 안전성 검증
        for section, fields in _SQL_FIELDS.items():
            items = parsed.get(section, [])
            if not isinstance(items, list):
                continue
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                for field in fields:
                    value = item.get(field)
                    if value:
                        try:
                            _validate_sql_fragment(str(value), f"{section}[{idx}].{field}")
                        except ValueError as exc:
                            errors.append(str(exc))

        # 4) 조인 순환 참조 검증 (self-join 차단)
        joins = parsed.get("joins", [])
        if isinstance(joins, list):
            for idx, j in enumerate(joins):
                if not isinstance(j, dict):
                    continue
                left = j.get("left_entity_id")
                right = j.get("right_entity_id")
                if left and right and left == right:
                    errors.append(
                        f"joins[{idx}]: left_entity_id와 right_entity_id가 동일합니다 "
                        f"(self-join 불가: '{left}')"
                    )

        return errors


class SemanticYamlExporter:
    """시멘틱 계약을 YAML로 내보낸다.

    SemanticStore의 카탈로그 데이터를 읽어 구조화된 YAML 문자열을 생성한다.
    """

    def __init__(self, store: SemanticStore) -> None:
        self._store = store

    def export(
        self,
        tenant_id: str,
        domain_id: str | None = None,
        case_id: str | None = None,
    ) -> str:
        """시멘틱 계약 전체를 YAML 문자열로 내보낸다.

        Args:
            tenant_id: 테넌트 식별자
            domain_id: 필터링할 도메인 (None이면 전체)
            case_id: 필터링할 케이스 (None이면 전체)

        Returns:
            YAML 형식 문자열
        """
        now = datetime.now(timezone.utc).isoformat()

        # 데이터 수집 — SemanticStore의 list 메서드 활용
        concepts = self._store.list_concepts(tenant_id, case_id=case_id, limit=500)
        entities = self._store.list_entities(tenant_id, case_id=case_id, limit=500)
        measures = self._store.list_measures(tenant_id, case_id=case_id, limit=500)
        dimensions = self._store.list_dimensions(tenant_id, case_id=case_id, limit=500)
        joins = self._store.list_join_contracts(tenant_id, case_id=case_id, limit=500)
        grains = self._store.list_grain_contracts(tenant_id, case_id=case_id, limit=500)
        quality = self._store.list_quality_contracts(tenant_id, case_id=case_id, limit=500)
        context_packs = self._store.list_context_packs(tenant_id, case_id=case_id, limit=500)

        # domain_id 필터 (개념 기준)
        if domain_id:
            concepts = [c for c in concepts if c.get("domain_id") == domain_id]

        # 개념별 용어 수집 — 효율적 벌크 조회
        concept_ids = [c["concept_id"] for c in concepts]
        terms_by_concept: dict[str, list[dict]] = {}
        if concept_ids:
            # list_terms_by_concepts_bulk가 있으면 사용, 없으면 개별 조회
            if hasattr(self._store, "list_terms_by_concepts_bulk"):
                all_terms = self._store.list_terms_by_concepts_bulk(tenant_id, concept_ids)
                for t in all_terms:
                    cid = t.get("concept_id", "")
                    terms_by_concept.setdefault(cid, []).append(t)
            else:
                for cid in concept_ids:
                    terms = self._store.list_terms_by_concept(tenant_id, cid)
                    if terms:
                        terms_by_concept[cid] = terms

        # YAML 문서 구성
        doc: dict[str, Any] = {
            "axiom_semantic_version": "1.0",
            "exported_at": now,
            "domain_id": domain_id or "all",
        }

        # 개념 직렬화 (용어 포함)
        if concepts:
            doc["concepts"] = []
            for c in concepts:
                entry = self._serialize_concept(c)
                cid = c["concept_id"]
                if cid in terms_by_concept:
                    entry["terms"] = [
                        self._serialize_term(t) for t in terms_by_concept[cid]
                    ]
                doc["concepts"].append(entry)

        # 엔티티 직렬화
        if entities:
            doc["entities"] = [self._serialize_entity(e) for e in entities]

        # 지표 직렬화
        if measures:
            doc["measures"] = [self._serialize_measure(m) for m in measures]

        # 차원 직렬화
        if dimensions:
            doc["dimensions"] = [self._serialize_dimension(d) for d in dimensions]

        # 조인 직렬화
        if joins:
            doc["joins"] = [self._serialize_join(j) for j in joins]

        # 그레인 직렬화
        if grains:
            doc["grains"] = [self._serialize_grain(g) for g in grains]

        # 품질 계약 직렬화
        if quality:
            doc["quality_contracts"] = [self._serialize_quality(q) for q in quality]

        # 컨텍스트 팩 직렬화
        if context_packs:
            doc["context_packs"] = [self._serialize_context_pack(cp) for cp in context_packs]

        # YAML 생성 — 한글 깨짐 방지 + 깔끔한 출력
        header = (
            "# Axiom Semantic Contract Export\n"
            f"# Exported at: {now}\n"
            f"# Domain: {domain_id or 'all'}\n\n"
        )
        yaml_body = yaml.dump(
            doc,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120,
        )
        return header + yaml_body

    # ── 직렬화 헬퍼: 내부 메타 필드(tenant_id 등)를 제거 ──

    @staticmethod
    def _clean(row: dict[str, Any], exclude: set[str] | None = None) -> dict[str, Any]:
        """내보내기에 불필요한 내부 필드를 제거한다."""
        _exclude = {"tenant_id", "case_id", "created_at", "updated_at"}
        if exclude:
            _exclude |= exclude
        result = {}
        for k, v in row.items():
            if k in _exclude:
                continue
            # datetime → ISO 문자열 변환
            if isinstance(v, datetime):
                result[k] = v.isoformat()
            # JSONB가 문자열로 올 수도 있음
            elif isinstance(v, str) and k in ("grain_key_set", "default_filters",
                                                "included_concept_ids", "included_measure_ids",
                                                "included_dimension_ids", "allowed_join_ids",
                                                "banned_join_ids", "temporal_rules",
                                                "answer_guardrails"):
                try:
                    result[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    result[k] = v
            else:
                result[k] = v
        return result

    def _serialize_concept(self, c: dict) -> dict:
        return self._clean(c)

    def _serialize_term(self, t: dict) -> dict:
        return self._clean(t, exclude={"term_id"})

    def _serialize_entity(self, e: dict) -> dict:
        return self._clean(e)

    def _serialize_measure(self, m: dict) -> dict:
        return self._clean(m)

    def _serialize_dimension(self, d: dict) -> dict:
        return self._clean(d)

    def _serialize_join(self, j: dict) -> dict:
        return self._clean(j)

    def _serialize_grain(self, g: dict) -> dict:
        return self._clean(g)

    def _serialize_quality(self, q: dict) -> dict:
        return self._clean(q)

    def _serialize_context_pack(self, cp: dict) -> dict:
        return self._clean(cp)


class SemanticYamlImporter:
    """YAML에서 시멘틱 계약을 가져온다 (upsert).

    전략: ID가 이미 존재하면 update, 없으면 create.
    순서: concepts → entities → measures/dimensions → joins → grains → quality → context_packs
    (FK 의존성 순서를 지킨다.)
    """

    def __init__(self, store: SemanticStore) -> None:
        self._store = store
        self._validator = SemanticYamlValidator()

    def import_yaml(
        self,
        tenant_id: str,
        yaml_content: str,
        dry_run: bool = False,
        git_sha: str | None = None,
        case_id: str = "",
    ) -> dict[str, Any]:
        """YAML 문자열을 파싱하여 시멘틱 계약을 DB에 upsert한다.

        Args:
            tenant_id: 테넌트 식별자
            yaml_content: YAML 문자열
            dry_run: True이면 검증만 수행하고 DB 변경 없음
            git_sha: Git 커밋 SHA (릴리스 추적용)
            case_id: 기본 케이스 ID (YAML에 없으면 사용)

        Returns:
            결과 요약 dict (created, updated, skipped, errors)
        """
        # 1) YAML 파싱
        try:
            parsed = yaml.safe_load(yaml_content)
        except yaml.YAMLError as exc:
            return {
                "created": {},
                "updated": {},
                "skipped": {},
                "errors": [f"YAML 파싱 오류: {exc}"],
                "dry_run": dry_run,
            }

        if not isinstance(parsed, dict):
            return {
                "created": {},
                "updated": {},
                "skipped": {},
                "errors": ["YAML 루트가 딕셔너리가 아닙니다"],
                "dry_run": dry_run,
            }

        # 2) 검증
        validation_errors = self._validator.validate(parsed)
        if validation_errors:
            return {
                "created": {},
                "updated": {},
                "skipped": {},
                "errors": validation_errors,
                "dry_run": dry_run,
            }

        # 3) dry_run이면 여기서 종료
        if dry_run:
            # 각 섹션별 항목 수를 미리보기로 반환
            preview: dict[str, int] = {}
            for section in _REQUIRED_FIELDS:
                items = parsed.get(section, [])
                if isinstance(items, list):
                    preview[section] = len(items)
            return {
                "created": preview,
                "updated": {},
                "skipped": {},
                "errors": [],
                "dry_run": True,
            }

        # 4) upsert 실행 — FK 의존성 순서
        result: dict[str, dict[str, int]] = {
            "created": {},
            "updated": {},
            "skipped": {},
        }
        errors: list[str] = []

        # 4a) 개념
        self._upsert_concepts(tenant_id, parsed.get("concepts", []), case_id, result, errors)

        # 4b) 엔티티
        self._upsert_entities(tenant_id, parsed.get("entities", []), case_id, result, errors)

        # 4c) 지표
        self._upsert_measures(tenant_id, parsed.get("measures", []), case_id, result, errors)

        # 4d) 차원
        self._upsert_dimensions(tenant_id, parsed.get("dimensions", []), case_id, result, errors)

        # 4e) 조인
        self._upsert_joins(tenant_id, parsed.get("joins", []), case_id, result, errors)

        # 4f) 그레인
        self._upsert_grains(tenant_id, parsed.get("grains", []), case_id, result, errors)

        # 4g) 품질 계약
        self._upsert_quality_contracts(tenant_id, parsed.get("quality_contracts", []), case_id, result, errors)

        # 4h) 컨텍스트 팩
        self._upsert_context_packs(tenant_id, parsed.get("context_packs", []), case_id, result, errors)

        # 5) git_sha 기록 — import 완료 시 릴리스 레코드 생성
        if git_sha and not errors:
            self._record_import_release(tenant_id, git_sha, result)

        return {
            "created": result["created"],
            "updated": result["updated"],
            "skipped": result["skipped"],
            "errors": errors,
            "dry_run": False,
            "git_commit_sha": git_sha,
        }

    # ── Upsert 헬퍼 메서드들 ──

    def _upsert_concepts(
        self, tenant_id: str, items: list, case_id: str,
        result: dict, errors: list,
    ) -> None:
        """개념 upsert — 용어(terms) 포함"""
        if not isinstance(items, list):
            return
        created = 0
        updated = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            cid = item.get("concept_id", "")
            terms = item.pop("terms", [])  # 용어는 별도 처리
            data = {**item, "case_id": item.get("case_id", case_id)}
            try:
                existing = self._store.get_concept(tenant_id, cid)
                if existing:
                    # update — concept_id, case_id 등 PK 필드 제외
                    update_data = {k: v for k, v in data.items()
                                   if k not in ("concept_id", "case_id", "tenant_id") and v is not None}
                    if update_data:
                        self._store.update_concept(tenant_id, cid, update_data)
                        updated += 1
                else:
                    self._store.create_concept(tenant_id, data)
                    created += 1

                # 용어 처리 — 기존 용어와 중복되지 않는 것만 추가
                if isinstance(terms, list) and terms:
                    existing_terms = self._store.list_terms_by_concept(tenant_id, cid)
                    existing_forms = {
                        (t.get("surface_form"), t.get("language"))
                        for t in existing_terms
                    }
                    new_terms = []
                    for t in terms:
                        if isinstance(t, dict):
                            key = (t.get("surface_form"), t.get("language", "ko"))
                            if key not in existing_forms:
                                new_terms.append({
                                    "concept_id": cid,
                                    "surface_form": t.get("surface_form", ""),
                                    "language": t.get("language", "ko"),
                                    "term_type": t.get("term_type", "primary"),
                                    "confidence": t.get("confidence", 1.0),
                                })
                    if new_terms:
                        self._store.create_terms_bulk(tenant_id, new_terms)

            except Exception as exc:
                errors.append(f"concepts[{cid}]: {exc}")

        if created:
            result["created"]["concepts"] = created
        if updated:
            result["updated"]["concepts"] = updated

    def _upsert_entities(
        self, tenant_id: str, items: list, case_id: str,
        result: dict, errors: list,
    ) -> None:
        """엔티티 upsert"""
        if not isinstance(items, list):
            return
        created = 0
        updated = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            eid = item.get("entity_id", "")
            data = {**item, "case_id": item.get("case_id", case_id)}
            try:
                existing = self._store.get_entity(tenant_id, eid)
                if existing:
                    update_data = {k: v for k, v in data.items()
                                   if k not in ("entity_id", "case_id", "tenant_id") and v is not None}
                    if update_data:
                        self._store.update_entity(tenant_id, eid, update_data)
                        updated += 1
                else:
                    self._store.create_entity(tenant_id, data)
                    created += 1
            except Exception as exc:
                errors.append(f"entities[{eid}]: {exc}")

        if created:
            result["created"]["entities"] = created
        if updated:
            result["updated"]["entities"] = updated

    def _upsert_measures(
        self, tenant_id: str, items: list, case_id: str,
        result: dict, errors: list,
    ) -> None:
        """지표 upsert"""
        if not isinstance(items, list):
            return
        created = 0
        updated = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            mid = item.get("measure_id", "")
            data = {**item, "case_id": item.get("case_id", case_id)}
            try:
                existing = self._store.get_measure(tenant_id, mid)
                if existing:
                    update_data = {k: v for k, v in data.items()
                                   if k not in ("measure_id", "case_id", "tenant_id") and v is not None}
                    if update_data:
                        self._store.update_measure(tenant_id, mid, update_data)
                        updated += 1
                else:
                    self._store.create_measure(tenant_id, data)
                    created += 1
            except Exception as exc:
                errors.append(f"measures[{mid}]: {exc}")

        if created:
            result["created"]["measures"] = created
        if updated:
            result["updated"]["measures"] = updated

    def _upsert_dimensions(
        self, tenant_id: str, items: list, case_id: str,
        result: dict, errors: list,
    ) -> None:
        """차원 upsert"""
        if not isinstance(items, list):
            return
        created = 0
        updated = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            did = item.get("dimension_id", "")
            data = {**item, "case_id": item.get("case_id", case_id)}
            try:
                existing = self._store.get_dimension(tenant_id, did)
                if existing:
                    update_data = {k: v for k, v in data.items()
                                   if k not in ("dimension_id", "case_id", "tenant_id") and v is not None}
                    if update_data:
                        self._store.update_dimension(tenant_id, did, update_data)
                        updated += 1
                else:
                    self._store.create_dimension(tenant_id, data)
                    created += 1
            except Exception as exc:
                errors.append(f"dimensions[{did}]: {exc}")

        if created:
            result["created"]["dimensions"] = created
        if updated:
            result["updated"]["dimensions"] = updated

    def _upsert_joins(
        self, tenant_id: str, items: list, case_id: str,
        result: dict, errors: list,
    ) -> None:
        """조인 계약 upsert"""
        if not isinstance(items, list):
            return
        created = 0
        updated = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            jid = item.get("join_id", "")
            data = {**item, "case_id": item.get("case_id", case_id)}
            try:
                existing = self._store.get_join_contract(tenant_id, jid)
                if existing:
                    update_data = {k: v for k, v in data.items()
                                   if k not in ("join_id", "case_id", "tenant_id",
                                                "left_entity_id", "right_entity_id") and v is not None}
                    if update_data:
                        self._store.update_join_contract(tenant_id, jid, update_data)
                        updated += 1
                else:
                    self._store.create_join_contract(tenant_id, data)
                    created += 1
            except Exception as exc:
                errors.append(f"joins[{jid}]: {exc}")

        if created:
            result["created"]["joins"] = created
        if updated:
            result["updated"]["joins"] = updated

    def _upsert_grains(
        self, tenant_id: str, items: list, case_id: str,
        result: dict, errors: list,
    ) -> None:
        """그레인 계약 upsert"""
        if not isinstance(items, list):
            return
        created = 0
        updated = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            gid = item.get("grain_id", "")
            data = {**item, "case_id": item.get("case_id", case_id)}
            try:
                existing = self._store.get_grain_contract(tenant_id, gid)
                if existing:
                    update_data = {k: v for k, v in data.items()
                                   if k not in ("grain_id", "case_id", "tenant_id", "entity_id") and v is not None}
                    if update_data:
                        self._store.update_grain_contract(tenant_id, gid, update_data)
                        updated += 1
                else:
                    self._store.create_grain_contract(tenant_id, data)
                    created += 1
            except Exception as exc:
                errors.append(f"grains[{gid}]: {exc}")

        if created:
            result["created"]["grains"] = created
        if updated:
            result["updated"]["grains"] = updated

    def _upsert_quality_contracts(
        self, tenant_id: str, items: list, case_id: str,
        result: dict, errors: list,
    ) -> None:
        """품질 계약 upsert — 품질 계약은 update 메서드가 없으므로 create only + skip 중복"""
        if not isinstance(items, list):
            return
        created = 0
        skipped = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            qid = item.get("quality_contract_id", "")
            data = {**item, "case_id": item.get("case_id", case_id)}
            try:
                self._store.create_quality_contract(tenant_id, data)
                created += 1
            except ValueError as exc:
                # 이미 존재하면 skip
                if "이미 존재합니다" in str(exc):
                    skipped += 1
                else:
                    errors.append(f"quality_contracts[{qid}]: {exc}")
            except Exception as exc:
                errors.append(f"quality_contracts[{qid}]: {exc}")

        if created:
            result["created"]["quality_contracts"] = created
        if skipped:
            result["skipped"]["quality_contracts"] = skipped

    def _upsert_context_packs(
        self, tenant_id: str, items: list, case_id: str,
        result: dict, errors: list,
    ) -> None:
        """컨텍스트 팩 upsert"""
        if not isinstance(items, list):
            return
        created = 0
        updated = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            cpid = item.get("context_pack_id", "")
            data = {**item, "case_id": item.get("case_id", case_id)}
            try:
                existing = self._store.get_context_pack(tenant_id, cpid)
                if existing:
                    update_data = {k: v for k, v in data.items()
                                   if k not in ("context_pack_id", "case_id", "tenant_id") and v is not None}
                    if update_data:
                        self._store.update_context_pack(tenant_id, cpid, update_data)
                        updated += 1
                else:
                    self._store.create_context_pack(tenant_id, data)
                    created += 1
            except Exception as exc:
                errors.append(f"context_packs[{cpid}]: {exc}")

        if created:
            result["created"]["context_packs"] = created
        if updated:
            result["updated"]["context_packs"] = updated

    def _record_import_release(
        self, tenant_id: str, git_sha: str, result: dict,
    ) -> None:
        """import 완료 시 git_commit_sha를 포함한 릴리스 메모를 로그로 기록한다.

        semantic_releases 테이블에 git_commit_sha 컬럼이 추가되면
        해당 컬럼에도 기록한다. 현재는 로그 기록만 수행.
        """
        total_created = sum(result.get("created", {}).values())
        total_updated = sum(result.get("updated", {}).values())
        logger.info(
            "semantic_yaml_import_complete",
            git_commit_sha=git_sha,
            tenant_id=tenant_id,
            created=total_created,
            updated=total_updated,
        )
