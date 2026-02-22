import { useState } from 'react';
import { Button } from '@/components/ui/button';

export interface ReviewComment {
  id: string;
  author: string;
  text: string;
  createdAt: string;
}

interface ReviewPanelProps {
  comments: ReviewComment[];
  onAddComment?: (text: string) => void;
  readonly?: boolean;
}

/** 리뷰 코멘트 쓰레드. 인라인 앵커는 선택 사항으로 추후 확장. */
export function ReviewPanel({ comments, onAddComment, readonly }: ReviewPanelProps) {
  const [newComment, setNewComment] = useState('');

  const handleSubmit = () => {
    const trimmed = newComment.trim();
    if (trimmed && onAddComment) {
      onAddComment(trimmed);
      setNewComment('');
    }
  };

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
      <h3 className="mb-3 text-sm font-semibold text-white">리뷰 코멘트</h3>
      <ul className="mb-4 space-y-2 max-h-48 overflow-auto">
        {comments.map((c) => (
          <li key={c.id} className="rounded border border-neutral-800 bg-neutral-950 p-2 text-sm">
            <span className="font-medium text-neutral-300">{c.author}</span>
            <span className="ml-2 text-neutral-500 text-xs">
              {new Date(c.createdAt).toLocaleString('ko-KR')}
            </span>
            <p className="mt-1 text-neutral-400">{c.text}</p>
          </li>
        ))}
        {comments.length === 0 && (
          <li className="text-sm text-neutral-500">아직 코멘트가 없습니다.</li>
        )}
      </ul>
      {!readonly && onAddComment && (
        <div className="flex gap-2">
          <input
            type="text"
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            placeholder="코멘트 입력..."
            className="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-white placeholder:text-neutral-500"
          />
          <Button type="button" variant="secondary" size="sm" onClick={handleSubmit}>
            추가
          </Button>
        </div>
      )}
    </div>
  );
}
