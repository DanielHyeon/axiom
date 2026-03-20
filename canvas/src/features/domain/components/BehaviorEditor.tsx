/**
 * BehaviorEditor — Behavior 코드 편집기 (Monaco 통합)
 *
 * REST API, JavaScript, Python, DMN 4가지 유형을 지원.
 * KAIR BehaviorDialog.vue의 코드 편집 영역을 React + Monaco + Tailwind로 재구현.
 */

import React, { useState, useCallback, useEffect } from 'react';
import MonacoEditor from 'react-monaco-editor';
import {
  Play,
  Save,
  Loader2,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { Behavior, BehaviorType, BehaviorTrigger } from '../types/domain';

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface BehaviorEditorProps {
  /** 다이얼로그 열림 상태 */
  open: boolean;
  /** 닫기 콜백 */
  onClose: () => void;
  /** 저장 콜백 */
  onSave: (behavior: Omit<Behavior, 'id'>) => void;
  /** 실행 테스트 콜백 */
  onTest?: (behavior: Omit<Behavior, 'id'>) => void;
  /** 편집 대상 (null이면 새로 생성) */
  initialBehavior?: Behavior | null;
  /** 사용 가능한 컬럼 이름 (inputFields 선택용) */
  availableColumns?: string[];
  /** 저장 중 로딩 */
  isSaving?: boolean;
}

// ──────────────────────────────────────
// 기본 코드 템플릿
// ──────────────────────────────────────

const DEFAULT_CODE: Record<BehaviorType, string> = {
  rest: '',
  javascript: `// Behavior: JavaScript 코드
// input: { fieldName: value, ... }
// output: 결과 객체를 return

function execute(input) {
  const result = {};
  // 로직 작성
  return result;
}
`,
  python: `# Behavior: Python 코드
# input: dict { field_name: value, ... }
# output: dict 결과

def execute(input: dict) -> dict:
    result = {}
    # 로직 작성
    return result
`,
  dmn: `<!-- DMN Decision Table -->
<definitions xmlns="https://www.omg.org/spec/DMN/20191111/MODEL/">
</definitions>
`,
};

// ──────────────────────────────────────
// 유틸: Monaco 언어 매핑
// ──────────────────────────────────────

function getMonacoLanguage(type: BehaviorType): string {
  switch (type) {
    case 'javascript':
      return 'javascript';
    case 'python':
      return 'python';
    case 'dmn':
      return 'xml';
    default:
      return 'plaintext';
  }
}

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const BehaviorEditor: React.FC<BehaviorEditorProps> = ({
  open,
  onClose,
  onSave,
  onTest,
  initialBehavior,
  availableColumns = [],
  isSaving = false,
}) => {
  // 폼 상태
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [type, setType] = useState<BehaviorType>('rest');
  const [trigger, setTrigger] = useState<BehaviorTrigger>('manual');
  const [code, setCode] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [httpMethod, setHttpMethod] = useState('POST');
  const [enabled, setEnabled] = useState(true);

  // 초기값 로드
  useEffect(() => {
    if (initialBehavior) {
      setName(initialBehavior.name);
      setDescription(initialBehavior.description ?? '');
      setType(initialBehavior.type);
      setTrigger(initialBehavior.trigger);
      setCode(initialBehavior.code);
      setEndpoint(initialBehavior.endpoint ?? '');
      setHttpMethod(initialBehavior.httpMethod ?? 'POST');
      setEnabled(initialBehavior.enabled);
    } else {
      setName('');
      setDescription('');
      setType('rest');
      setTrigger('manual');
      setCode('');
      setEndpoint('');
      setHttpMethod('POST');
      setEnabled(true);
    }
  }, [initialBehavior, open]);

  // 타입 변경 시 기본 코드 템플릿 적용
  const handleTypeChange = useCallback(
    (newType: BehaviorType) => {
      setType(newType);
      if (!code || code === DEFAULT_CODE[type]) {
        setCode(DEFAULT_CODE[newType]);
      }
    },
    [code, type],
  );

  // 저장
  const handleSave = useCallback(() => {
    if (!name.trim()) return;
    onSave({
      name: name.trim(),
      description: description.trim() || undefined,
      type,
      trigger,
      code,
      endpoint: type === 'rest' ? endpoint : undefined,
      httpMethod: type === 'rest' ? httpMethod : undefined,
      enabled,
    });
  }, [name, description, type, trigger, code, endpoint, httpMethod, enabled, onSave]);

  // 테스트 실행
  const handleTest = useCallback(() => {
    if (!onTest) return;
    onTest({
      name: name.trim(),
      description: description.trim() || undefined,
      type,
      trigger,
      code,
      endpoint: type === 'rest' ? endpoint : undefined,
      httpMethod: type === 'rest' ? httpMethod : undefined,
      enabled,
    });
  }, [name, description, type, trigger, code, endpoint, httpMethod, enabled, onTest]);

  const isEdit = !!initialBehavior;

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-card border border-border rounded-lg w-[720px] max-h-[85vh] overflow-auto shadow-xl">
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div>
            <h2 className="text-sm font-semibold text-foreground">
              {isEdit ? 'Behavior 편집' : 'Behavior 추가'}
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              ObjectType에 연결할 행동(Behavior)을 정의합니다.
            </p>
          </div>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground text-lg leading-none p-1">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* 폼 본문 */}
        <div className="p-5 space-y-4">
          {/* 이름 + 설명 */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">이름 *</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="behavior_name"
                className="h-8 text-sm"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">설명</label>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="이 행동의 설명..."
                className="h-8 text-sm"
              />
            </div>
          </div>

          {/* 타입 + 트리거 */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">유형</label>
              <Select value={type} onValueChange={(v) => handleTypeChange(v as BehaviorType)}>
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="rest">REST API 호출</SelectItem>
                  <SelectItem value="javascript">JavaScript 코드</SelectItem>
                  <SelectItem value="python">Python 코드</SelectItem>
                  <SelectItem value="dmn">DMN 규칙</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">트리거</label>
              <Select value={trigger} onValueChange={(v) => setTrigger(v as BehaviorTrigger)}>
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="manual">수동 실행</SelectItem>
                  <SelectItem value="on_create">생성 시 실행</SelectItem>
                  <SelectItem value="on_update">수정 시 실행</SelectItem>
                  <SelectItem value="scheduled">스케줄 실행</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* REST API 전용 필드 */}
          {type === 'rest' && (
            <div className="grid grid-cols-4 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground">HTTP 메서드</label>
                <Select value={httpMethod} onValueChange={setHttpMethod}>
                  <SelectTrigger className="h-8 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="GET">GET</SelectItem>
                    <SelectItem value="POST">POST</SelectItem>
                    <SelectItem value="PUT">PUT</SelectItem>
                    <SelectItem value="PATCH">PATCH</SelectItem>
                    <SelectItem value="DELETE">DELETE</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="col-span-3 space-y-1.5">
                <label className="text-xs text-muted-foreground">엔드포인트 URL</label>
                <Input
                  value={endpoint}
                  onChange={(e) => setEndpoint(e.target.value)}
                  placeholder="https://api.example.com/predict"
                  className="h-8 text-sm"
                />
              </div>
            </div>
          )}

          {/* 코드 편집기 (JS / Python / DMN) */}
          {type !== 'rest' && (
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">코드</label>
              <div className="border border-border rounded-lg overflow-hidden">
                <MonacoEditor
                  height="300"
                  language={getMonacoLanguage(type)}
                  value={code}
                  onChange={(v) => setCode(v)}
                  theme="vs-dark"
                  options={{
                    minimap: { enabled: false },
                    fontSize: 13,
                    lineNumbers: 'on',
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    tabSize: 2,
                    wordWrap: 'on',
                  }}
                />
              </div>
            </div>
          )}
        </div>

        {/* 푸터 */}
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-border">
          {onTest && (
            <Button variant="outline" size="sm" onClick={handleTest} disabled={!name.trim()}>
              <Play className="h-3.5 w-3.5 mr-1" />
              테스트 실행
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={onClose}>
            취소
          </Button>
          <Button size="sm" onClick={handleSave} disabled={!name.trim() || isSaving}>
            {isSaving ? (
              <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
            ) : (
              <Save className="h-3.5 w-3.5 mr-1" />
            )}
            {isEdit ? '수정' : '생성'}
          </Button>
        </div>
      </div>
    </div>
  );
};
