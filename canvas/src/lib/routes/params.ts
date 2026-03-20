import { useParams } from 'react-router-dom';

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function parseUuid(value: string | undefined, paramName: string): string {
  if (value == null || value === '') {
    throw new Error(`Missing required param: ${paramName}`);
  }
  if (!UUID_REGEX.test(value)) {
    throw new Error(`Invalid UUID format for param: ${paramName}`);
  }
  return value;
}

/**
 * /cases/:caseId 구간에서 caseId를 타입 안전하게 반환.
 * 잘못된 UUID면 에러를 던져 ErrorBoundary에서 처리할 수 있게 한다.
 */
export function useCaseParams(): { caseId: string } {
  const { caseId } = useParams<{ caseId: string }>();
  return { caseId: parseUuid(caseId, 'caseId') };
}

/**
 * /cases/:caseId/documents/:docId 구간에서 caseId, docId 반환.
 */
export function useDocumentParams(): { caseId: string; docId: string } {
  const { caseId, docId } = useParams<{ caseId: string; docId: string }>();
  return {
    caseId: parseUuid(caseId, 'caseId'),
    docId: parseUuid(docId, 'docId'),
  };
}

/**
 * /process-designer/:boardId 구간에서 boardId 반환.
 */
export function useBoardParams(): { boardId: string } {
  const { boardId } = useParams<{ boardId: string }>();
  return { boardId: parseUuid(boardId, 'boardId') };
}
