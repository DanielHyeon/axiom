import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import MonacoEditor from 'react-monaco-editor';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

// Configure Monaco Worker for Vite
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
(self as any).MonacoEnvironment = {
    getWorker() {
        return new editorWorker();
    },
};

const initialContent = `# 이해관계자 목록

## 1. 핵심 이해관계자

| 참여자 | 예산 | 순위 |
|--------|------|------|
| 운영팀 | 12억 | 1순위|
| 전략팀 | 5억  | 1순위|

## 2. 일반 이해관계자

| 참여자 | 예산 | 비율 |
|--------|------|------|
| 마케팅 | 50억 | 35%  |
| 개발팀 | 30억 | 21%  |
| 디자인 | 20억 | 14%  |
`;

export function DocumentEditorPage() {
    const navigate = useNavigate();
    const [content, setContent] = useState(initialContent);
    const [comments] = useState([
        { id: '1', line: '7-8', author: '박전문가', time: '2시간 전', text: '운영팀 예산 확인 필요합니다. 12억이 맞는지?', resolved: false },
        { id: '2', line: '14', author: '박전문가', time: '1시간 전', text: '마케팅 비율 재계산 해주세요', resolved: true },
        { id: '3', line: '전체', author: '박전문가', time: '30분 전', text: '전반적으로 양호하나 금액 검증 필요', resolved: false },
    ]);

    const editorOptions = {
        selectOnLineNumbers: true,
        minimap: { enabled: false },
        wordWrap: 'on' as const,
        fontSize: 14,
        theme: 'vs-dark'
    };

    return (
        <div className="flex h-[calc(100vh-8rem)] flex-col space-y-4">
            <div className="flex justify-between items-center">
                <div className="flex items-center space-x-4">
                    <Button variant="ghost" onClick={() => navigate('/documents')}>← Back</Button>
                    <h1 className="text-xl font-bold flex items-center gap-2">
                        📄 이해관계자 목록 v3 <Badge variant="secondary">검토 중</Badge>
                    </h1>
                </div>
                <div className="space-x-2">
                    <Button variant="outline">Diff 보기</Button>
                    <Button variant="outline">히스토리</Button>
                    <Button variant="default" className="bg-green-600 hover:bg-green-700">승인</Button>
                </div>
            </div>

            <div className="flex-1 flex gap-4 overflow-hidden">
                {/* Editor Pane */}
                <div className="flex-1 border border-neutral-800 rounded-md overflow-hidden bg-[#1e1e1e] flex flex-col">
                    <div className="p-2 bg-neutral-900 border-b border-neutral-800 flex justify-end space-x-2">
                        <Button variant="ghost" size="sm">되돌리기</Button>
                        <Button variant="secondary" size="sm">저장</Button>
                    </div>
                    <div className="flex-1">
                        <MonacoEditor
                            language="markdown"
                            theme="vs-dark"
                            value={content}
                            options={editorOptions}
                            onChange={(newValue) => setContent(newValue)}
                            width="100%"
                            height="100%"
                        />
                    </div>
                </div>

                {/* Review Panel */}
                <div className="w-80 border border-neutral-800 rounded-md bg-neutral-900 flex flex-col">
                    <div className="p-4 border-b border-neutral-800">
                        <h3 className="font-semibold text-sm mb-2">리뷰 패널</h3>
                        <p className="text-xs text-neutral-400">검토자: 박전문가</p>
                        <p className="text-xs text-neutral-400">기한: 2024-03-15</p>
                    </div>

                    <div className="flex-1 overflow-auto p-4 space-y-4">
                        <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">
                            ─── 코멘트 ({comments.length}) ───
                        </h4>

                        {comments.map(c => (
                            <div key={c.id} className={"p-3 rounded-md text-sm " + (c.resolved ? 'bg-neutral-800/50 opacity-70' : 'bg-neutral-800')}>
                                <div className="flex justify-between mb-1">
                                    <span className="font-medium text-blue-400 text-xs">💬 줄 {c.line}</span>
                                    {c.resolved && <span className="text-green-500 text-xs text-right">✓ 해결됨</span>}
                                </div>
                                <p className="text-neutral-200 mb-2">"{c.text}"</p>
                                <div className="flex justify-between items-center text-xs text-neutral-500">
                                    <span>- {c.author}</span>
                                    <span>{c.time}</span>
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="p-4 border-t border-neutral-800">
                        <Button variant="secondary" className="w-full">코멘트 추가</Button>
                    </div>
                </div>
            </div>
        </div>
    );
}
