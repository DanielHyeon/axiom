/**
 * Phase C3 스텁: Yjs 실시간 협업 (커서 공유·동시 편집).
 * 연동 시: Yjs Provider + WS 또는 외부 서비스, awareness.
 */
export const collaborationEnabled = false;

export function useCollaboration(_boardId: string | undefined) {
  return { enabled: false, users: [] as { id: string; name?: string }[] };
}
