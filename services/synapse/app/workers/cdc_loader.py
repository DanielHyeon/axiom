"""Kafka CDC 로더 -- Debezium CDC 이벤트를 Neo4j로 동기화.

외부 운영 DB의 변경사항(INSERT/UPDATE/DELETE)을 실시간으로
Neo4j 인스턴스 노드에 반영한다.

KAIR loader/main.py를 Axiom 패턴으로 이식.
독립 워커로 실행되며, FastAPI 서버와는 별도 프로세스.

사용법:
  python -m app.workers.cdc_loader

환경변수:
  KAFKA_BOOTSTRAP_SERVERS=localhost:9092
  KAFKA_GROUP_ID=axiom-neo4j-loader
  KAFKA_TOPICS=dbserver.public.*
  NEO4J_URI=bolt://localhost:7687
  NEO4J_USER=neo4j
  NEO4J_PASSWORD=password
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
import logging
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cdc_loader")

# Kafka 의존성 — 선택적 (설치되지 않으면 graceful 실패)
try:
    from confluent_kafka import Consumer, KafkaError, KafkaException  # type: ignore
    HAS_KAFKA = True
except ImportError:
    HAS_KAFKA = False
    Consumer = None  # type: ignore
    KafkaError = None  # type: ignore
    KafkaException = None  # type: ignore

# Neo4j 의존성 — 선택적
try:
    from neo4j import GraphDatabase  # type: ignore
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False
    GraphDatabase = None  # type: ignore


# ── 설정값 (환경변수에서 로드) ──────────────────────────────────────


def _env(key: str, default: str = "") -> str:
    """환경변수 읽기 헬퍼"""
    return os.environ.get(key, default)


# ── Debezium 이벤트 파서 ────────────────────────────────────────────


def parse_debezium_event(raw_value: bytes | str) -> dict[str, Any] | None:
    """Debezium CDC 이벤트를 파싱한다.

    Debezium 이벤트 형식:
      {
        "op": "c" | "u" | "d" | "r",
        "before": {...} | null,
        "after": {...} | null,
        "source": {"table": "...", "schema": "..."}
      }

    Returns:
        파싱된 딕셔너리 또는 None (파싱 실패 시)
    """
    if raw_value is None:
        return None
    try:
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("utf-8")
        data = json.loads(raw_value)
        # payload 래핑된 경우 처리 (Debezium envelope)
        if "payload" in data and isinstance(data["payload"], dict):
            data = data["payload"]
        return data
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("CDC 이벤트 파싱 실패: %s", exc)
        return None


def extract_table_name(event: dict[str, Any]) -> str:
    """Debezium 이벤트에서 소스 테이블명을 추출한다."""
    source = event.get("source", {})
    schema = source.get("schema", "public")
    table = source.get("table", "unknown")
    return f"{schema}.{table}"


def build_neo4j_label(table_name: str) -> str:
    """테이블명에서 Neo4j 노드 레이블을 생성한다.

    예: 'public.order_items' → 'OrderItems'
    """
    # 스키마 접두사 제거, 스네이크→파스칼 변환
    raw = table_name.split(".")[-1] if "." in table_name else table_name
    parts = [p for p in raw.strip().split("_") if p]
    return "".join(p.capitalize() for p in parts) if parts else "Unknown"


# ── Neo4j 작업 빌더 ────────────────────────────────────────────────


def build_neo4j_query(event: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Debezium 이벤트를 Neo4j Cypher 쿼리로 변환한다.

    Returns:
        (cypher_query, params) 튜플 또는 None (처리 불가 시)
    """
    op = event.get("op")
    if op not in ("c", "u", "d", "r"):
        logger.warning("알 수 없는 CDC 오퍼레이션: %s", op)
        return None

    table = extract_table_name(event)
    label = build_neo4j_label(table)

    if op in ("c", "r", "u"):
        # INSERT / READ(snapshot) / UPDATE → MERGE + SET
        after = event.get("after")
        if not after or not isinstance(after, dict):
            logger.warning("after 필드 없음 (op=%s, table=%s)", op, table)
            return None

        # 프라이머리 키 결정 — id 필드 또는 첫 번째 필드
        pk_field = "id"
        if pk_field not in after:
            # 첫 번째 필드를 PK로 사용
            pk_field = next(iter(after.keys()), None)
            if not pk_field:
                return None

        pk_value = after[pk_field]
        # SET 절용 속성 (PK 제외)
        props = {k: v for k, v in after.items() if v is not None}

        cypher = (
            f"MERGE (n:Instance:{label} {{{pk_field}: $pk_value}}) "
            f"SET n += $props, n._cdc_table = $table, n._cdc_updated_at = datetime()"
        )
        return cypher, {"pk_value": pk_value, "props": props, "table": table}

    elif op == "d":
        # DELETE → 노드 삭제
        before = event.get("before")
        if not before or not isinstance(before, dict):
            logger.warning("before 필드 없음 (op=d, table=%s)", table)
            return None

        pk_field = "id"
        if pk_field not in before:
            pk_field = next(iter(before.keys()), None)
            if not pk_field:
                return None

        pk_value = before[pk_field]
        cypher = f"MATCH (n:Instance:{label} {{{pk_field}: $pk_value}}) DETACH DELETE n"
        return cypher, {"pk_value": pk_value}

    return None


# ── CDC 로더 메인 클래스 ────────────────────────────────────────────


class CDCLoader:
    """Kafka CDC 이벤트를 Neo4j로 동기화하는 워커.

    Debezium이 캡처한 DB 변경사항을 실시간으로 Neo4j Instance 노드에 반영한다.
    """

    def __init__(
        self,
        kafka_bootstrap: str | None = None,
        kafka_group_id: str | None = None,
        kafka_topics: str | None = None,
        neo4j_uri: str | None = None,
        neo4j_user: str | None = None,
        neo4j_password: str | None = None,
        poll_timeout: float = 1.0,
    ):
        self._kafka_bootstrap = kafka_bootstrap or _env("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self._kafka_group_id = kafka_group_id or _env("KAFKA_GROUP_ID", "axiom-neo4j-loader")
        self._kafka_topics = kafka_topics or _env("KAFKA_TOPICS", "dbserver.public.*")
        self._neo4j_uri = neo4j_uri or _env("NEO4J_URI", "bolt://localhost:7687")
        self._neo4j_user = neo4j_user or _env("NEO4J_USER", "neo4j")
        self._neo4j_password = neo4j_password or _env("NEO4J_PASSWORD", "password")
        self._poll_timeout = poll_timeout

        self._consumer = None
        self._driver = None
        self._running = False

        # 통계
        self._processed = 0
        self._errors = 0
        self._skipped = 0

    def connect(self) -> None:
        """Kafka Consumer + Neo4j Driver 초기화"""
        if not HAS_KAFKA:
            raise ImportError(
                "confluent_kafka 패키지가 설치되지 않았습니다. "
                "pip install confluent-kafka 로 설치하세요."
            )
        if not HAS_NEO4J:
            raise ImportError(
                "neo4j 패키지가 설치되지 않았습니다. "
                "pip install neo4j 로 설치하세요."
            )

        # Kafka Consumer 생성
        config = {
            "bootstrap.servers": self._kafka_bootstrap,
            "group.id": self._kafka_group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
            "auto.commit.interval.ms": 5000,
        }
        self._consumer = Consumer(config)

        # 토픽 구독 (와일드카드 지원)
        topics = [t.strip() for t in self._kafka_topics.split(",") if t.strip()]
        if any("*" in t for t in topics):
            # 정규식 패턴으로 구독
            pattern = topics[0].replace(".", r"\.").replace("*", ".*")
            self._consumer.subscribe([f"^{pattern}"])
            logger.info("Kafka 토픽 패턴 구독: %s", pattern)
        else:
            self._consumer.subscribe(topics)
            logger.info("Kafka 토픽 구독: %s", topics)

        # Neo4j Driver 생성
        self._driver = GraphDatabase.driver(
            self._neo4j_uri,
            auth=(self._neo4j_user, self._neo4j_password),
        )
        # 연결 테스트
        self._driver.verify_connectivity()
        logger.info("Neo4j 연결 성공: %s", self._neo4j_uri)

    def process_event(self, raw_value: bytes | str) -> bool:
        """단일 CDC 이벤트를 처리한다.

        Returns:
            처리 성공 여부
        """
        event = parse_debezium_event(raw_value)
        if event is None:
            self._skipped += 1
            return False

        query_result = build_neo4j_query(event)
        if query_result is None:
            self._skipped += 1
            return False

        cypher, params = query_result
        table = extract_table_name(event)
        op = event.get("op", "?")

        try:
            with self._driver.session() as session:
                session.run(cypher, **params)
            self._processed += 1
            logger.debug("CDC 처리 완료: op=%s table=%s", op, table)
            return True
        except Exception as exc:
            self._errors += 1
            logger.error("Neo4j 쿼리 실패: %s (op=%s, table=%s)", exc, op, table)
            return False

    def run(self) -> None:
        """메인 이벤트 루프 — SIGINT/SIGTERM으로 종료."""
        self._running = True

        # 시그널 핸들러 등록 (graceful shutdown)
        def _shutdown(signum, frame):
            logger.info("종료 시그널 수신 (signal=%s), 셧다운 시작...", signum)
            self._running = False

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        logger.info(
            "CDC 로더 시작 — bootstrap=%s, group=%s",
            self._kafka_bootstrap,
            self._kafka_group_id,
        )

        try:
            while self._running:
                msg = self._consumer.poll(timeout=self._poll_timeout)
                if msg is None:
                    continue

                if msg.error():
                    error = msg.error()
                    if error.code() == KafkaError._PARTITION_EOF:
                        # 파티션 끝 도달 — 정상
                        continue
                    logger.error("Kafka 에러: %s", error)
                    continue

                # 메시지 처리
                self.process_event(msg.value())

        except KeyboardInterrupt:
            logger.info("키보드 인터럽트로 종료")
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        """리소스 정리"""
        logger.info(
            "CDC 로더 종료 — 처리: %d, 에러: %d, 스킵: %d",
            self._processed,
            self._errors,
            self._skipped,
        )
        if self._consumer:
            try:
                self._consumer.close()
            except Exception:
                pass
        if self._driver:
            try:
                self._driver.close()
            except Exception:
                pass

    @property
    def stats(self) -> dict[str, int]:
        """현재 처리 통계 반환"""
        return {
            "processed": self._processed,
            "errors": self._errors,
            "skipped": self._skipped,
        }


# ── 스크립트 직접 실행 ──────────────────────────────────────────────


def main() -> None:
    """CDC 로더 엔트리포인트"""
    if not HAS_KAFKA:
        logger.error("confluent_kafka 미설치. pip install confluent-kafka")
        sys.exit(1)
    if not HAS_NEO4J:
        logger.error("neo4j 미설치. pip install neo4j")
        sys.exit(1)

    loader = CDCLoader()
    loader.connect()
    loader.run()


if __name__ == "__main__":
    main()
