/**
 * Mermaid ERD 렌더러 컴포넌트 — shared re-export
 *
 * 실제 구현은 features/datasource/components/MermaidERDRenderer.tsx에 있다.
 * nl2sql 등 다른 feature에서 직접 datasource를 참조하지 않도록
 * shared 레이어를 통해 접근한다.
 */

export { MermaidERDRenderer } from '@/features/datasource/components/MermaidERDRenderer';
