# Axiom Core - 트랜잭션 경계와 Saga 패턴

## 이 문서가 답하는 질문

- 트랜잭션 경계는 어디에 설정되고, 왜 그렇게 나뉘는가?
- Saga 보상 트랜잭션은 실제로 어떻게 구현되는가?
- Event Outbox와 비즈니스 로직의 원자성은 어떻게 보장하는가?

<!-- affects: backend, data -->
<!-- requires-update: 01_architecture/bpm-engine.md, 06_data/event-outbox.md -->

---

## 1. 트랜잭션 경계 원칙

### 1.1 기본 원칙

```
[결정] 트랜잭션 경계는 Service Layer에서 관리한다.
[근거] Application Layer(Service)가 유스케이스 단위의 작업 범위를 알고 있다.
       Router는 HTTP 요청/응답만, Domain은 규칙만 담당한다.

[결정] 하나의 API 호출 = 하나의 DB 트랜잭션을 기본으로 한다.
[예외] BPM 프로세스 실행처럼 여러 단계를 거치는 경우 Saga 패턴을 적용한다.

[결정] Event Outbox INSERT는 반드시 비즈니스 로직과 같은 트랜잭션에서 수행한다.
[근거] 별도 트랜잭션이면 "데이터는 저장됐지만 이벤트는 유실"되는 상황이 발생한다.
```

### 1.2 트랜잭션 경계 매핑

| 유스케이스 | 트랜잭션 범위 | 패턴 |
|-----------|------------|------|
| 케이스 생성 | 단일 트랜잭션 (케이스 INSERT + 이벤트 INSERT) | 기본 |
| 워크아이템 제출 | 단일 트랜잭션 (상태 UPDATE + 다음 워크아이템 INSERT + 이벤트 INSERT) | 기본 |
| 프로세스 시작 | 단일 트랜잭션 (인스턴스 INSERT + 첫 워크아이템 INSERT + 이벤트 INSERT) | 기본 |
| 에이전트 태스크 실행 | Saga (LLM 호출 -> DB 저장 -> 실패 시 보상) | Saga |
| 문서 추출 + 온톨로지 갱신 | Saga (추출 -> DB 저장 -> Synapse API -> 실패 시 보상) | Saga |
| 재작업 | Saga (상태 롤백 + 후속 작업 보상 + 이벤트 발행) | Saga |

---

## 2. 트랜잭션 구현

### 2.1 기본 트랜잭션 패턴

```python
# app/services/case_service.py

class CaseService:
    async def create_case(self, data: CaseCreateSchema) -> CaseResponse:
        """케이스 생성 - 단일 트랜잭션"""
        async with get_session() as session:
            # 1. 비즈니스 검증
            await self._validate_case_data(session, data)

            # 2. 케이스 INSERT
            case = Case(**data.model_dump(), tenant_id=get_current_tenant_id())
            session.add(case)

            # 3. Event Outbox INSERT (같은 트랜잭션!)
            await EventPublisher.publish(
                session=session,
                event_type="CASE_CREATED",
                aggregate_type="case",
                aggregate_id=case.id,
                payload={"case_id": str(case.id), "name": case.name},
            )

            # 4. 커밋 (비즈니스 + 이벤트 원자적)
            await session.commit()
            await session.refresh(case)

        return CaseResponse.model_validate(case)
```

### 2.2 Saga 트랜잭션 패턴

```python
# app/services/process_service.py

class ProcessService:
    async def execute_agent_task(
        self,
        workitem_id: str,
    ) -> dict:
        """에이전트 태스크 실행 - Saga 패턴"""
        saga_log = []

        try:
            # Step 1: 워크아이템 상태 변경 (DB 트랜잭션)
            async with get_session() as session:
                workitem = await self._get_workitem(session, workitem_id)
                workitem.status = "IN_PROGRESS"
                await session.commit()
                saga_log.append(("workitem_status", workitem_id, "IN_PROGRESS"))

            # Step 2: LLM 에이전트 실행 (외부 호출 - 트랜잭션 밖)
            result = await self.agent_service.execute(workitem)
            saga_log.append(("agent_execution", workitem_id, result))

            # Step 3: 결과 저장 (DB 트랜잭션)
            async with get_session() as session:
                workitem = await self._get_workitem(session, workitem_id)
                workitem.result_data = result
                workitem.status = "SUBMITTED"

                await EventPublisher.publish(
                    session=session,
                    event_type="WORKITEM_AGENT_COMPLETED",
                    aggregate_type="workitem",
                    aggregate_id=workitem.id,
                    payload={"result": result},
                )
                await session.commit()

            return result

        except Exception as e:
            # Saga 보상: 역순으로 롤백
            await self._compensate_saga(saga_log, str(e))
            raise

    async def _compensate_saga(self, saga_log: list, error: str):
        """Saga 보상 - 실행된 단계를 역순으로 롤백"""
        for step_name, entity_id, data in reversed(saga_log):
            try:
                if step_name == "workitem_status":
                    async with get_session() as session:
                        workitem = await self._get_workitem(session, entity_id)
                        workitem.status = "TODO"  # 원래 상태로 복원
                        await session.commit()

                elif step_name == "agent_execution":
                    # 에이전트 실행 결과는 DB에 아직 저장 안 됐으므로 보상 불필요
                    pass

            except Exception as comp_error:
                logger.error(
                    f"Saga compensation failed: step={step_name}, "
                    f"entity={entity_id}, error={comp_error}"
                )
                # 보상 실패 시 관리자 알림
                await self._alert_compensation_failure(entity_id, step_name, str(comp_error))
```

> **보상 실패 시 DLQ**: 모든 보상 단계가 실패하면, 실패 정보가 DLQ에 기록되고 CRITICAL 알림이 발생한다. DLQ 아키텍처 및 Incident Runbook은 [resilience-patterns.md](../01_architecture/resilience-patterns.md) §5, §8을 참조한다.

### 2.3 문서 추출 + 온톨로지 갱신 Saga

Core에서 문서를 추출하고 Synapse를 통해 Neo4j에 온톨로지를 커밋하는 크로스 서비스 Saga이다.

#### 7단계 Saga 흐름

```
Step 1: 문서 상태 변경 (PENDING → EXTRACTING)         [Core DB 트랜잭션]
  보상: 상태 복원 (EXTRACTING → PENDING)

Step 2: OCR/텍스트 추출                                [외부 호출]
  보상: skip (DB 저장 전이므로 메모리에만 존재)

Step 3: 추출 결과 Core DB 저장                         [Core DB 트랜잭션]
  보상: 추출 결과 DELETE

Step 4: Synapse 온톨로지 추출 요청                     [HTTP, 비동기]
  (POST /api/v3/synapse/extraction/documents/{doc_id}/extract-ontology)
  보상: Synapse 추출 task가 진행 중이면 취소

Step 5: Synapse 결과 폴링                              [HTTP, 폴링]
  (GET /api/v3/synapse/extraction/documents/{doc_id}/ontology-status)
  보상: 없음 (읽기 전용)

Step 6: Neo4j 커밋 결과 확인 + committed 목록 수집      [HTTP]
  (GET /api/v3/synapse/extraction/documents/{doc_id}/ontology-result)
  보상: Synapse revert API로 committed 엔티티/관계 삭제
  (POST /api/v3/synapse/extraction/documents/{doc_id}/revert-extraction)

Step 7: Core에 온톨로지 매핑 결과 저장 + 이벤트 발행    [Core DB 트랜잭션]
  보상: 매핑 결과 DELETE + EXTRACTION_REVERTED 이벤트 발행
```

#### 구현 코드

```python
# app/services/document_service.py

class DocumentExtractionSaga:
    """문서 추출 + 온톨로지 갱신 Saga"""

    def __init__(self, saga_executor: SagaExecutor, synapse_client):
        self.saga = saga_executor
        self.synapse = synapse_client

    async def execute(
        self,
        doc_id: str,
        case_id: str,
        tenant_id: str,
    ) -> dict:
        context = SagaContext(
            proc_inst_id=f"extraction-{doc_id}",
            tenant_id=tenant_id,
        )

        try:
            # Step 1: 문서 상태 변경
            async with get_session() as session:
                doc = await self._get_document(session, doc_id)
                doc.status = "EXTRACTING"
                await session.commit()

            await self.saga.execute_step(context, step_name="doc_status", result={
                "doc_id": doc_id,
                "previous_status": "PENDING",
            }, compensation=CompensationAction(
                type="db_rollback",
                server="core",
                tool="revert_doc_status",
                params={"doc_id": doc_id, "status": "PENDING"},
            ))

            # Step 2: OCR/텍스트 추출
            extracted_text = await self._extract_text(doc_id)
            await self.saga.execute_step(context, step_name="ocr_extract", result={
                "text_length": len(extracted_text),
            }, compensation=None)  # 메모리에만 존재, 보상 불필요

            # Step 3: 추출 결과 DB 저장
            async with get_session() as session:
                extraction = DocumentExtraction(
                    doc_id=doc_id,
                    raw_text=extracted_text,
                    status="EXTRACTED",
                )
                session.add(extraction)
                await session.commit()
                extraction_id = extraction.id

            await self.saga.execute_step(context, step_name="save_extraction", result={
                "extraction_id": str(extraction_id),
            }, compensation=CompensationAction(
                type="db_rollback",
                server="core",
                tool="delete_extraction",
                params={"extraction_id": "$output.extraction_id"},
            ))

            # Step 4: Synapse 온톨로지 추출 요청 (비동기)
            task_response = await self.synapse.post(
                f"/documents/{doc_id}/extract-ontology",
                json={
                    "case_id": case_id,
                    "options": {
                        "auto_commit_threshold": 0.75,
                        "extract_entities": True,
                        "extract_relations": True,
                    },
                },
            )
            task_id = task_response["data"]["task_id"]

            await self.saga.execute_step(context, step_name="synapse_request", result={
                "task_id": task_id,
            }, compensation=CompensationAction(
                type="api_call",
                server="synapse",
                tool="cancel_extraction",
                params={"task_id": "$output.task_id"},
            ))

            # Step 5: 결과 폴링 (최대 600초)
            await self._poll_until_complete(doc_id, timeout=600)
            await self.saga.execute_step(context, step_name="poll_status", result={},
                compensation=None)  # 읽기 전용

            # Step 6: committed 엔티티/관계 수집
            result = await self.synapse.get(
                f"/documents/{doc_id}/ontology-result?status=committed"
            )
            committed_entity_ids = [
                e["id"] for e in result["data"]["entities"]
                if e["status"] == "committed"
            ]
            committed_relation_ids = [
                r["id"] for r in result["data"]["relations"]
                if r["status"] == "committed"
            ]

            await self.saga.execute_step(context, step_name="neo4j_commit", result={
                "committed_entity_ids": committed_entity_ids,
                "committed_relation_ids": committed_relation_ids,
            }, compensation=CompensationAction(
                type="api_call",
                server="synapse",
                tool="revert_extraction",
                params={
                    "doc_id": doc_id,
                    "entity_ids": "$output.committed_entity_ids",
                    "relation_ids": "$output.committed_relation_ids",
                },
                max_retries=3,
            ))

            # Step 7: Core에 매핑 결과 저장 + 이벤트 발행
            async with get_session() as session:
                doc = await self._get_document(session, doc_id)
                doc.ontology_mapped = True
                doc.entity_count = len(committed_entity_ids)
                doc.relation_count = len(committed_relation_ids)

                await EventPublisher.publish(
                    session=session,
                    event_type="EXTRACTION_COMPLETED",
                    aggregate_type="document",
                    aggregate_id=doc_id,
                    payload={
                        "doc_id": doc_id,
                        "entity_count": len(committed_entity_ids),
                        "relation_count": len(committed_relation_ids),
                    },
                )
                await session.commit()

            context.status = SagaStatus.COMPLETED
            return {
                "doc_id": doc_id,
                "entities": len(committed_entity_ids),
                "relations": len(committed_relation_ids),
                "pending_review": result["data"]["extraction_summary"]["pending_review"],
            }

        except Exception as e:
            # Saga 보상: 역순으로 롤백
            await self.saga.compensate(context)
            raise
```

#### 비동기 Saga 특이사항

```
[사실] Step 4→5는 비동기 흐름이다. task_id 기반 폴링으로 완료를 확인하며,
       폴링 타임아웃(600초) 초과 시 Saga 실패 + 보상을 시작한다.

[사실] Synapse의 auto_commit_threshold(0.75) 이상인 엔티티만 Neo4j에 자동 커밋된다.
       pending_review 상태 엔티티는 Neo4j에 반영되지 않으므로 보상 대상이 아니다.

[사실] Step 6 보상(revert_extraction)은 committed 엔티티의 neo4j_node_id를 기반으로
       타겟 삭제를 수행한다. Revert API 상세는 Synapse extraction-api.md §3.8을 참조한다.

[결정] 보상 실패 시 DLQ 에스컬레이션은 §2.2의 기존 패턴과 동일하게 적용한다.
```

---

## 3. 동시성 제어

### 3.1 낙관적 잠금 (Optimistic Locking)

```python
# app/models/base.py

class BaseModel(Base):
    __abstract__ = True
    version = Column(Integer, default=1, nullable=False)

# 사용
async def update_workitem(session, workitem_id, updates):
    workitem = await session.get(Workitem, workitem_id)
    current_version = workitem.version

    for key, value in updates.items():
        setattr(workitem, key, value)
    workitem.version += 1

    # flush 시 version 불일치 감지
    try:
        await session.flush()
    except StaleDataError:
        raise ConflictError("다른 사용자가 이미 이 작업을 수정했습니다.")
```

### 3.2 비관적 잠금 (FOR UPDATE)

```python
# Event Outbox 폴링 시 사용 - 중복 처리 방지
events = await session.execute(
    select(EventOutbox)
    .where(EventOutbox.status == "PENDING")
    .order_by(EventOutbox.created_at)
    .limit(100)
    .with_for_update(skip_locked=True)  # 다른 Worker가 처리 중인 건 건너뜀
)
```

---

## 4. 트랜잭션 경계 규칙 요약

```
[필수] Service 메서드 하나 = 트랜잭션 하나 (기본 원칙)
[필수] Event Outbox INSERT는 비즈니스 로직과 같은 세션에서 수행
[필수] 외부 서비스 호출(LLM, MCP, 다른 모듈)은 DB 트랜잭션 밖에서 수행
[필수] Saga 보상 시 각 보상 단계는 독립 트랜잭션으로 실행
[금지] Router 핸들러에서 트랜잭션 관리 (Service에 위임)
[금지] 하나의 트랜잭션에서 여러 외부 서비스 호출 (장시간 트랜잭션 금지)
[금지] 트랜잭션 내 sleep 또는 긴 대기
```

---

## 근거

- K-AIR process-gpt-completion-main (process_service.py, compensation_handler.py)
- ADR-005: Saga 보상 트랜잭션 패턴
- 01_architecture/bpm-engine.md (Saga 보상 상세)
