import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
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
| 전략팀 | 5억 | 1순위|

## 2. 일반 이해관계자

| 참여자 | 예산 | 비율 |
|--------|------|------|
| 마케팅 | 50억 | 35% |
| 개발팀 | 30억 | 21% |
| 디자인 | 20억 | 14% |
`;

export function DocumentEditorPage() {
 const navigate = useNavigate();
 const { t } = useTranslation();
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
 <div className="flex h-[calc(100vh-8rem)] flex-col space-y-3 md:space-y-4 px-2 md:px-0">
 <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
 <div className="flex items-center space-x-2 md:space-x-4 min-w-0">
 <Button variant="ghost" size="sm" onClick={() => navigate('/documents')}>← {t('common.back')}</Button>
 <h1 className="text-base md:text-xl font-bold flex items-center gap-2 truncate">
 이해관계자 목록 v3 <Badge variant="secondary">{t('documents.status.in_review')}</Badge>
 </h1>
 </div>
 <div className="flex gap-1 md:space-x-2 shrink-0">
 <Button variant="outline" size="sm">{t('documents.editor.viewDiff')}</Button>
 <Button variant="outline" size="sm">{t('documents.editor.history')}</Button>
 <Button variant="default" size="sm" className="bg-success hover:bg-green-700">{t('common.approve')}</Button>
 </div>
 </div>

 <div className="flex-1 flex flex-col lg:flex-row gap-3 md:gap-4 overflow-hidden">
 {/* Editor Pane */}
 <div className="flex-1 border border-border rounded-md overflow-hidden bg-card flex flex-col min-h-[300px]">
 <div className="p-2 bg-card border-b border-border flex justify-end space-x-2">
 <Button variant="ghost" size="sm">{t('documents.editor.undo')}</Button>
 <Button variant="secondary" size="sm">{t('common.save')}</Button>
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
 <div className="w-full lg:w-80 shrink-0 border border-border rounded-md bg-card flex flex-col max-h-[40vh] lg:max-h-none">
 <div className="p-4 border-b border-border">
 <h3 className="font-semibold text-sm mb-2">{t('documents.editor.reviewPanel')}</h3>
 <p className="text-xs text-muted-foreground">{t('documents.editor.reviewer')}: 박전문가</p>
 <p className="text-xs text-muted-foreground">{t('documents.editor.deadline')}: 2024-03-15</p>
 </div>

 <div className="flex-1 overflow-auto p-4 space-y-4">
 <h4 className="text-xs font-semibold text-foreground0 uppercase tracking-wider mb-2">
 ─── {t('documents.editor.comments')} ({comments.length}) ───
 </h4>

 {comments.map(c => (
 <div key={c.id} className={"p-3 rounded-md text-sm " + (c.resolved ? 'bg-muted/50 opacity-70' : 'bg-muted')}>
 <div className="flex justify-between mb-1">
 <span className="font-medium text-primary text-xs">{t('documents.editor.line')} {c.line}</span>
 {c.resolved && <span className="text-success text-xs text-right">{t('documents.editor.resolved')}</span>}
 </div>
 <p className="text-foreground mb-2">"{c.text}"</p>
 <div className="flex justify-between items-center text-xs text-foreground0">
 <span>- {c.author}</span>
 <span>{c.time}</span>
 </div>
 </div>
 ))}
 </div>

 <div className="p-4 border-t border-border">
 <Button variant="secondary" className="w-full">{t('documents.editor.addComment')}</Button>
 </div>
 </div>
 </div>
 </div>
 );
}
