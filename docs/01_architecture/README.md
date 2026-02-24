# Architecture

크로스서비스 아키텍처 원칙과 설계 문서입니다.

## Documents

| Document | Description |
|----------|-------------|
| [semantic-layer.md](semantic-layer.md) | Semantic Layer 아키텍처 — Weaver/Synapse/Vision 책임 경계 정의 |
| [4source-ingestion.md](4source-ingestion.md) | 4-Source Ingestion — RDBMS, Legacy Code, Docs/Audio, External API 통합 파이프라인 |
| [self-verification.md](self-verification.md) | Self-Verification — 20% 샘플링 자동검증, 회귀 테스트, HITL 피드백 루프 |

## Service-Level Architecture

각 서비스의 상세 아키텍처는 서비스별 docs에 있습니다:

- [Core Architecture](../../services/core/docs/01_architecture/)
- [Oracle Architecture](../../services/oracle/docs/01_architecture/)
- [Synapse Architecture](../../services/synapse/docs/01_architecture/)
- [Vision Architecture](../../services/vision/docs/01_architecture/)
- [Weaver Architecture](../../services/weaver/docs/01_architecture/)
- [Canvas Architecture](../../apps/canvas/docs/01_architecture/)
