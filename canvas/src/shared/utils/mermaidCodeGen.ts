/**
 * Mermaid ERD 코드 생성 유틸리티 — shared re-export
 *
 * 실제 구현은 features/datasource/utils/mermaidCodeGen.ts에 있다.
 * nl2sql 등 다른 feature에서 직접 datasource를 참조하지 않도록
 * shared 레이어를 통해 접근한다.
 */

export { generateMermaidERCode, getConnectedTables } from '@/features/datasource/utils/mermaidCodeGen';
