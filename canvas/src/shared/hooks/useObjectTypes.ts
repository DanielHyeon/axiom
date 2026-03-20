/**
 * ObjectType 조회 훅 — shared re-export
 *
 * 실제 구현은 features/domain/hooks/useObjectTypes.ts에 있다.
 * object-explorer 등 다른 feature에서 직접 domain을 참조하지 않도록
 * shared 레이어를 통해 접근한다.
 */

export { useObjectTypeList, useObjectTypeDetail } from '@/features/domain/hooks/useObjectTypes';
