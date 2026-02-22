/** 검토 대기 패널 (역할별 표시). Phase 1 플레이스홀더. */
export function ApprovalQueuePanel() {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
      <h2 className="mb-4 text-lg font-semibold text-white">검토 대기</h2>
      <p className="text-sm text-neutral-500">승인/반려 대기 항목이 여기에 표시됩니다.</p>
    </div>
  );
}
