// features/process-designer/components/AiDiscoverDialog.tsx
// AI 프로세스 발견 다이얼로그 (설계 §7)
// 이벤트 로그 소스 선택 → discoverProcess API → 자동 배치

import { useState, useCallback } from 'react';
import { discoverProcess, type DiscoveredProcess, type DiscoverRequest } from '../api/processDesignerApi';

interface AiDiscoverDialogProps {
 open: boolean;
 onClose: () => void;
 onDiscover: (result: DiscoveredProcess) => void;
}

type DiscoverStep = 'input' | 'discovering' | 'done' | 'error';

export function AiDiscoverDialog({ open, onClose, onDiscover }: AiDiscoverDialogProps) {
 const [step, setStep] = useState<DiscoverStep>('input');
 const [error, setError] = useState<string | null>(null);

 const [sourceTable, setSourceTable] = useState('');
 const [timestampColumn, setTimestampColumn] = useState('timestamp');
 const [caseIdColumn, setCaseIdColumn] = useState('case_id');
 const [activityColumn, setActivityColumn] = useState('activity');
 const [algorithm, setAlgorithm] = useState<DiscoverRequest['algorithm']>('inductive');

 const handleDiscover = useCallback(async () => {
 if (!sourceTable.trim()) return;
 setStep('discovering');
 setError(null);

 try {
 const result = await discoverProcess({
 sourceTable: sourceTable.trim(),
 timestampColumn,
 caseIdColumn,
 activityColumn,
 algorithm,
 });
 setStep('done');
 onDiscover(result);
 onClose();
 } catch (e) {
 setError(e instanceof Error ? e.message : '프로세스 발견에 실패했습니다.');
 setStep('error');
 }
 }, [sourceTable, timestampColumn, caseIdColumn, activityColumn, algorithm, onDiscover, onClose]);

 const handleReset = useCallback(() => {
 setStep('input');
 setError(null);
 }, []);

 if (!open) return null;

 return (
 <div className="fixed inset-0 z-50 flex items-center justify-center bg-sidebar/60">
 <div className="bg-card border border-border rounded-lg w-[480px] max-h-[80vh] overflow-auto shadow-xl">
 {/* Header */}
 <div className="flex items-center justify-between px-5 py-4 border-b border-border">
 <h2 className="text-sm font-semibold text-foreground">AI 프로세스 발견</h2>
 <button
 type="button"
 onClick={onClose}
 className="text-foreground0 hover:text-foreground/80 text-lg leading-none"
 >
 &times;
 </button>
 </div>

 {/* Body */}
 <div className="p-5 space-y-4">
 {step === 'input' && (
 <>
 <p className="text-xs text-muted-foreground">
 이벤트 로그 데이터 소스를 지정하면 pm4py가 프로세스 모델을 자동으로 발견합니다.
 </p>

 <label className="block">
 <span className="text-xs text-muted-foreground">소스 테이블 *</span>
 <input
 type="text"
 value={sourceTable}
 onChange={(e) => setSourceTable(e.target.value)}
 placeholder="예: event_log"
 className="mt-1 w-full bg-muted border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-blue-500"
 />
 </label>

 <div className="grid grid-cols-2 gap-3">
 <label className="block">
 <span className="text-xs text-muted-foreground">타임스탬프 컬럼</span>
 <input
 type="text"
 value={timestampColumn}
 onChange={(e) => setTimestampColumn(e.target.value)}
 className="mt-1 w-full bg-muted border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-blue-500"
 />
 </label>
 <label className="block">
 <span className="text-xs text-muted-foreground">케이스 ID 컬럼</span>
 <input
 type="text"
 value={caseIdColumn}
 onChange={(e) => setCaseIdColumn(e.target.value)}
 className="mt-1 w-full bg-muted border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-blue-500"
 />
 </label>
 </div>

 <label className="block">
 <span className="text-xs text-muted-foreground">활동 컬럼</span>
 <input
 type="text"
 value={activityColumn}
 onChange={(e) => setActivityColumn(e.target.value)}
 className="mt-1 w-full bg-muted border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-blue-500"
 />
 </label>

 <label className="block">
 <span className="text-xs text-muted-foreground">알고리즘</span>
 <select
 value={algorithm}
 onChange={(e) => setAlgorithm(e.target.value as DiscoverRequest['algorithm'])}
 className="mt-1 w-full bg-muted border border-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-blue-500"
 >
 <option value="inductive">Inductive Miner (권장)</option>
 <option value="alpha">Alpha Miner</option>
 <option value="heuristic">Heuristic Miner</option>
 </select>
 </label>
 </>
 )}

 {step === 'discovering' && (
 <div className="flex flex-col items-center py-8 gap-3">
 <div className="w-8 h-8 border-2 border-border border-t-blue-400 rounded-full animate-spin" />
 <p className="text-sm text-foreground/80">프로세스를 발견하는 중...</p>
 <p className="text-xs text-foreground0">pm4py가 이벤트 로그를 분석합니다.</p>
 </div>
 )}

 {step === 'error' && (
 <div className="py-4">
 <div className="bg-red-900/30 border border-red-700 rounded px-4 py-3 text-sm text-red-300">
 {error}
 </div>
 <button
 type="button"
 onClick={handleReset}
 className="mt-3 text-xs text-primary hover:text-primary/80"
 >
 다시 시도
 </button>
 </div>
 )}
 </div>

 {/* Footer */}
 {step === 'input' && (
 <div className="flex justify-end gap-2 px-5 py-4 border-t border-border">
 <button
 type="button"
 onClick={onClose}
 className="px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
 >
 취소
 </button>
 <button
 type="button"
 onClick={handleDiscover}
 disabled={!sourceTable.trim()}
 className="px-4 py-2 text-sm bg-primary text-white rounded disabled:opacity-50 hover:bg-primary"
 >
 프로세스 발견
 </button>
 </div>
 )}
 </div>
 </div>
 );
}
