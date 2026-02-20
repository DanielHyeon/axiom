# Voice-to-Ontology Pipeline (Audio Ingestion)

## 1. 목적
- 고객 상담(콜 센터), 기업 회의 음성 등 비정형 음성 데이터를 텍스트로 전환(ASR)한 후, 발화 내 개체(Entity)와 관계(Relation)를 추출하여 Synapse 4-Layer Ontology에 병합한다.
- 이 파이프라인은 기존 문서 기반 Knowledge Extraction Pipeline과 연계되며, 음성 데이터 특유의 보안/개인정보 처리 규칙을 강제한다.

## 2. 아키텍처 개요
본 파이프라인은 크게 3단계 비동기 워커 구조로 설계된다.

### 2.1 Audio Ingestion API (`POST /api/v1/synapse/ingest/audio`)
- **입력**: MP3/WAV/WebM 오디오 스트림 및 메타데이터(Session ID, 참가자 등)
- **응답**: Job ID 즉시 반환 (비동기 처리)
- **저장**: 오디오 파일은 암호화된 단기 객체 스토리지(S3 등)에 임시 보관되며, 처리 완료 시 즉시 파기(Retention: Max 24H)된다.

### 2.2 Speech-to-Text & Masking Worker
- **전사 (ASR)**: Whisper 등의 STT 모델을 활용하여 다화자 분리(Diarization) 및 타임스탬프 텍스트 변환 수행
- **보안 마스킹 (PII/Masking)**: 이름, 전화번호, 주민등록번호, 계좌번호 등 민감 개인정보(PII)를 사전 정의된 패턴식과 LLM 검증기 2-pass 방식으로 추출 전 완전 마스킹(`[PERSON]`, `[ID]`) 처리.

### 2.3 Ontology Extraction Worker
- 마스킹된 텍스트 스크립트를 기존 `extraction-pipeline.md`의 로직에 태워 Entity/Relation/Intent(의도) 모델을 추출.
- 회의나 상담 중 도출된 "정책 변경 동의", "조건부 승인" 등의 발화는 `Event` 또는 `Policy` 노드로 번역하여 4-Layer Ontology에 적재.

## 3. 보안 및 권한 정책
- 음성 데이터 파이프라인은 `vision` 및 통상적인 `semantic-layer` 쿼리에서 원본 오디오를 절대 반환하지 않는다. 오직 구조화된 Ontology 결과물만 제공된다.
- **마스킹 실패 처리**: 마스킹 Confidence가 99% 미만인 문장 세그먼트는 통째로 삭제 처리하거나 수동 HITL 감시관에게로만 라우팅된다.

## 4. 통과 기준 (Pass Criteria)
- 30분 분량의 음성 파일을 Ingest API 호출 시점부터 Ontology 반영까지 완료하는 데 소요되는 SLA가 30분 이내일 것.
- Golden QA 오디오 셋 대비 Entity 추출 Precision 및 Recall 지표가 85% 이상일 것.
- 민감 정보 누출(PII 누락) 테스트 시 마스킹 실패율 0%.
