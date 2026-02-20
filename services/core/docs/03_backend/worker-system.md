# Axiom Core - Worker 시스템

## 이 문서가 답하는 질문

- Core에는 어떤 Worker가 있고, 각각 무엇을 하는가?
- Worker의 라이프사이클과 에러 처리는 어떻게 관리되는가?
- Worker를 스케일링하려면 어떻게 해야 하는가?

<!-- affects: backend, operations -->
<!-- requires-update: 08_operations/deployment.md -->

---

## 1. Worker 목록

| Worker | 파일 | 입력 | 출력 | 간격/방식 |
|--------|------|------|------|----------|
| **sync** | `workers/sync.py` | event_outbox (DB 폴링) | Redis Streams | 5초 폴링 |
| **watch_cep** | `workers/watch_cep.py` | axiom:watches (Redis) | 알림 생성/발송 | Consumer Group |
| **ocr** | `workers/ocr.py` | axiom:workers (Redis) | 텍스트 추출 결과 (DB) | Consumer Group |
| **extract** | `workers/extract.py` | axiom:workers (Redis) | 구조화 데이터 (DB) | Consumer Group |
| **generate** | `workers/generate.py` | axiom:workers (Redis) | 생성된 문서 (MinIO) | Consumer Group |
| **event_log** | `workers/event_log.py` | axiom:workers (Redis) | 파싱된 이벤트 로그 (Synapse 전달) | Consumer Group |

---

## 2. Worker 공통 구조

```python
# app/workers/base.py

import asyncio
import signal

class BaseWorker:
    """모든 Worker의 기반 클래스"""

    def __init__(self, name: str):
        self.name = name
        self._running = True

    async def start(self):
        """Worker 시작 - 시그널 핸들러 등록"""
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._shutdown)

        logger.info(f"Worker {self.name} started")
        await self.run()

    async def run(self):
        """메인 루프 - 하위 클래스에서 구현"""
        raise NotImplementedError

    def _shutdown(self):
        """Graceful shutdown"""
        logger.info(f"Worker {self.name} shutting down...")
        self._running = False

    async def process_with_retry(self, func, *args, max_retries=3):
        """재시도 래퍼"""
        for attempt in range(max_retries):
            try:
                return await func(*args)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** attempt  # Exponential backoff
                logger.warning(
                    f"Retry {attempt+1}/{max_retries} for {func.__name__}: {e}"
                )
                await asyncio.sleep(wait)
```

> **DLQ 처리**: `max_retries` 초과 시 메시지는 Dead Letter Queue(`axiom:dlq:{stream}`)로 이동한다. DLQ 아키텍처, 관리 API, 재처리 절차는 [resilience-patterns.md](../01_architecture/resilience-patterns.md) §5를 참조한다.

---

## 3. Worker별 상세

### 3.1 Sync Worker (Event Outbox -> Redis Streams)

```
역할: DB의 event_outbox 테이블을 폴링하여 Redis Streams로 전달
입력: PostgreSQL event_outbox (status=PENDING)
출력: Redis Streams (axiom:events, axiom:watches, axiom:workers)
실행: 독립 프로세스, 인스턴스 1개 (SKIP LOCKED로 안전)
스케일링: 인스턴스 추가 시 SKIP LOCKED이 자동으로 작업 분배
```

### 3.2 Watch CEP Worker

```
역할: axiom:watches 스트림의 이벤트에 대해 CEP 룰을 평가하고 알림 발송
입력: Redis Streams axiom:watches (Consumer Group)
출력: 알림 (인앱 SSE, 이메일, SMS, Slack)
실행: 독립 프로세스, Consumer Group으로 N개 인스턴스 가능
스케일링: Consumer 추가 시 Redis가 자동으로 메시지 분배

특수사항:
  - 중복 알림 방지 (idempotency_key, 24시간 TTL)
  - CRITICAL 알림 1시간 미확인 시 에스컬레이션
  - 알림 발송 실패 시 3회 재시도 후 FAILED 기록
```

### 3.3 OCR Worker

```
역할: 업로드된 문서(PDF, 이미지)에서 텍스트를 추출
입력: Redis Streams axiom:workers (event_type=WORKER_OCR_REQUEST)
출력: 추출된 텍스트 (DB documents 테이블 업데이트)
실행: 독립 프로세스, CPU/메모리 집약적
스케일링: Consumer Group으로 N개 인스턴스 (문서당 1-5분)

처리 파이프라인:
  1. MinIO에서 원본 파일 다운로드
  2. 파일 유형 판별 (PDF, 이미지, HWP)
  3. Textract 또는 GPT-4o Vision으로 텍스트 추출
  4. 추출 결과 DB 저장 + 진행률 SSE 발송
  5. 완료 이벤트 발행 (WORKER_OCR_COMPLETED)
```

### 3.4 Extract Worker

```
역할: OCR된 텍스트를 구조화된 데이터로 변환
입력: Redis Streams axiom:workers (event_type=WORKER_EXTRACT_REQUEST)
출력: 구조화 데이터 (DB + pgvector 임베딩)
실행: 독립 프로세스, LLM API 호출 포함

처리 파이프라인:
  1. OCR 텍스트 로드
  2. 청킹 (800 토큰 단위, Recursive Splitter)
  3. GPT-4o Structured Output으로 구조화 추출
     - 엔티티 정보: 이해관계자, 수량, 유형, 근거
     - 자산 정보: 자산명, 평가액, 소재지
     - 일정 정보: 기한, 기일, 관련 프로세스
  4. pgvector 임베딩 생성 + 저장
  5. 완료 이벤트 발행 (WORKER_EXTRACT_COMPLETED)
```

### 3.5 Generate Worker

```
역할: 보고서/문서를 자동 생성
입력: Redis Streams axiom:workers (event_type=WORKER_GENERATE_REQUEST)
출력: 생성된 문서 (MinIO에 PDF/DOCX 저장)
실행: 독립 프로세스, LLM API + 문서 렌더링 포함

처리 파이프라인:
  1. 생성 요청 로드 (템플릿 + 데이터)
  2. LLM으로 문서 내용 생성
  3. 템플릿 렌더링 (Jinja2 + python-docx/reportlab)
  4. MinIO에 저장
  5. 완료 이벤트 발행 (WORKER_GENERATE_COMPLETED)
```

### 3.6 EventLog Worker

```
역할: 업로드된 이벤트 로그(XES/CSV)를 파싱, 검증, 청킹하여 Synapse로 스트리밍 전달
입력: Redis Streams axiom:workers (event_type=WORKER_EVENT_LOG_REQUEST)
출력: 파싱된 이벤트 로그 데이터 (Synapse REST API), 진행 상황 (Redis Streams SSE)
실행: 독립 프로세스, I/O + CPU 혼합 작업
스케일링: Consumer Group으로 N개 인스턴스 (파일 크기에 따라 1-30분)

처리 파이프라인:
  1. MinIO에서 업로드된 원본 파일 다운로드 (스트리밍)
  2. 파일 형식 판별 및 파서 선택 (XES/CSV)
  3. 형식 검증:
     - XES: XML 스키마 검증, trace/event 구조 확인
     - CSV: 필수 컬럼 존재 확인 (case_id, activity, timestamp)
     - 공통: 타임스탬프 파싱, 빈 값 처리
  4. 대용량 파일 청킹 (10,000 이벤트 단위)
  5. 청크별 Synapse REST API로 스트리밍 전달
  6. 진행률 Redis Streams 발행 (SSE -> Canvas)
  7. 완료 이벤트 발행 (PROCESS_LOG_INGESTED)

재시도 정책:
  - 최대 재시도: 3회
  - 백오프: Exponential (2초, 4초, 8초)
  - 재시도 대상: 네트워크 오류, Synapse 일시 장애
  - 재시도 불가: 형식 오류, 필수 컬럼 누락 (즉시 FAILED)

특수사항:
  - 파일을 메모리에 전체 로드하지 않음 (SAX 파서 / 스트리밍 CSV 리더)
  - 500MB 이상 파일은 10,000 이벤트 단위로 청킹
  - 청킹 시 동일 case의 이벤트가 분리되지 않도록 case 경계 보장
  - 진행 상황 업데이트: 10% 단위로 Redis Streams 발행

Synapse 연동:
  - 파싱된 이벤트는 Synapse Process Mining Engine (pm4py 기반)으로 전달되어
    프로세스 발견, 적합성 검사, 병목 분석 등에 활용된다.
  - Worker는 처리 완료 시 `axiom:process_mining` Redis Stream에 PROCESS_LOG_INGESTED
    이벤트를 발행하며, Synapse가 이를 구독하여 자동 디스커버리 파이프라인을 시작한다.
```

```python
# app/workers/event_log.py

import asyncio
from typing import AsyncIterator
from app.workers.base import BaseWorker
from app.core.redis_client import get_redis

class EventLogWorker(BaseWorker):
    """이벤트 로그 파싱/검증/스트리밍 Worker"""

    CONSUMER_GROUP = "event_log_group"
    CONSUMER_NAME = "event_log_worker_1"
    CHUNK_SIZE = 10_000  # events per chunk

    def __init__(self):
        super().__init__("event_log")

    async def run(self):
        redis = await get_redis()

        try:
            await redis.xgroup_create(
                "axiom:workers", self.CONSUMER_GROUP, id="0", mkstream=True
            )
        except Exception:
            pass

        while self._running:
            try:
                messages = await redis.xreadgroup(
                    groupname=self.CONSUMER_GROUP,
                    consumername=self.CONSUMER_NAME,
                    streams={"axiom:workers": ">"},
                    count=1,  # 파일 하나씩 처리 (대용량)
                    block=5000,
                )

                for stream, entries in messages:
                    for entry_id, data in entries:
                        if data.get("event_type") == "WORKER_EVENT_LOG_REQUEST":
                            await self.process_with_retry(
                                self._process_event_log, data
                            )
                        await redis.xack(
                            "axiom:workers", self.CONSUMER_GROUP, entry_id
                        )

            except Exception as e:
                logger.error(f"EventLogWorker error: {e}")
                await asyncio.sleep(1)

    async def _process_event_log(self, data: dict):
        """이벤트 로그 파일 처리 메인 로직"""
        event_log_id = data["aggregate_id"]
        payload = json.loads(data["payload"])

        # 1. MinIO에서 파일 스트리밍 다운로드
        file_stream = await self._download_from_minio(payload["file_path"])

        # 2. 형식 판별 및 파서 선택
        file_format = payload.get("format", "CSV")
        parser = self._get_parser(file_format)

        # 3. 형식 검증
        validation_result = await parser.validate(file_stream)
        if not validation_result.is_valid:
            await self._report_failure(
                event_log_id, validation_result.errors
            )
            return

        # 4. 파싱 + 청킹 + Synapse 전달
        total_events = 0
        chunk_count = 0

        async for chunk in parser.parse_chunks(
            file_stream, chunk_size=self.CHUNK_SIZE
        ):
            # Synapse REST API로 청크 전달
            await self._send_chunk_to_synapse(
                event_log_id, chunk, chunk_count
            )

            total_events += len(chunk)
            chunk_count += 1

            # 진행률 보고 (SSE)
            await self._report_progress(
                event_log_id, total_events, payload.get("estimated_total")
            )

        # 5. 완료 이벤트 발행
        await self._publish_completion(event_log_id, total_events, chunk_count)

    async def _send_chunk_to_synapse(
        self, event_log_id: str, chunk: list, chunk_index: int
    ):
        """청크를 Synapse 프로세스 마이닝 API로 전달"""
        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{SYNAPSE_URL}/api/v1/event-logs/ingest",
                json={
                    "event_log_id": event_log_id,
                    "chunk_index": chunk_index,
                    "events": chunk,
                },
            )
            response.raise_for_status()

    async def _report_progress(
        self, event_log_id: str, processed: int, total: int | None
    ):
        """진행 상황을 Redis Streams로 발행 (Canvas SSE 전달)"""
        redis = await get_redis()
        progress = (processed / total * 100) if total else 0
        await redis.xadd("axiom:process_mining", {
            "event_type": "MINING_PROGRESS",
            "event_log_id": event_log_id,
            "processed_events": str(processed),
            "progress_percent": f"{progress:.1f}",
        })

    def _get_parser(self, file_format: str):
        """파일 형식에 맞는 파서 반환"""
        if file_format == "XES":
            return XESStreamParser()
        elif file_format == "CSV":
            return CSVStreamParser()
        else:
            raise ValueError(f"Unsupported format: {file_format}")


class XESStreamParser:
    """XES 파일 스트리밍 파서 (SAX 기반, 메모리 효율적)"""

    async def validate(self, file_stream) -> ValidationResult:
        """XES XML 구조 검증: trace, event, timestamp 필수"""
        ...

    async def parse_chunks(
        self, file_stream, chunk_size: int
    ) -> AsyncIterator[list]:
        """XES 파일을 SAX 파서로 스트리밍 파싱, chunk_size 단위로 yield
        동일 trace(case)의 이벤트가 청크 경계에서 분리되지 않도록 보장"""
        ...


class CSVStreamParser:
    """CSV 파일 스트리밍 파서"""

    REQUIRED_COLUMNS = {"case_id", "activity", "timestamp"}

    async def validate(self, file_stream) -> ValidationResult:
        """CSV 헤더 검증: 필수 컬럼 존재 확인"""
        ...

    async def parse_chunks(
        self, file_stream, chunk_size: int
    ) -> AsyncIterator[list]:
        """CSV 파일을 행 단위로 스트리밍 파싱, chunk_size 단위로 yield
        동일 case_id의 이벤트가 청크 경계에서 분리되지 않도록 보장"""
        ...
```

---

## 4. Worker 실행 방법

```bash
# 개별 Worker 실행
python -m app.workers.sync
python -m app.workers.watch_cep
python -m app.workers.ocr
python -m app.workers.extract
python -m app.workers.generate
python -m app.workers.event_log

# Docker Compose에서 실행 (서비스별)
# docker-compose.yml에 각 Worker를 별도 서비스로 정의
```

---

## 5. 모니터링

```
[필수] 각 Worker는 처리한 메시지 수, 실패 수, 평균 처리 시간을 메트릭으로 노출한다.
[필수] Redis Streams의 Pending 메시지 수를 모니터링한다 (지연 감지).
[필수] Worker가 5분 이상 메시지를 처리하지 못하면 알림을 발송한다.
```

---

## 근거

- K-AIR 역설계 보고서 섹션 4.11.2 (Worker 구조)
- process-gpt-memento-main (문서 처리 로직)
- robo-data-text2sql-main/app/core/simple_cep.py (CEP 엔진)
- [08_operations/performance-monitoring.md](../08_operations/performance-monitoring.md) (Worker 메트릭, Pending 메시지 알림, Workers & Events Grafana 대시보드)
