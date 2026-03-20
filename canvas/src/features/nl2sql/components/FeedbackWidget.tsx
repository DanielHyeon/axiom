/**
 * FeedbackWidget — NL2SQL 결과에 대한 피드백 위젯.
 *
 * 결과 표시 후 사용자가 thumbs up/down을 누르고,
 * 선택적으로 SQL 수정이나 코멘트를 남길 수 있다.
 */
import { useState } from 'react';
import { ThumbsUp, ThumbsDown, Edit3 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { oracleApi } from '@/lib/api/clients';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

interface FeedbackWidgetProps {
  /** 쿼리 히스토리 ID — 피드백 저장 시 사용 */
  queryId: string | null | undefined;
  /** 생성된 SQL — 수정 입력의 기본값 */
  sql?: string;
}

type Rating = 'positive' | 'negative' | 'partial' | null;

export function FeedbackWidget({ queryId, sql }: FeedbackWidgetProps) {
  const [rating, setRating] = useState<Rating>(null);
  const [showCorrection, setShowCorrection] = useState(false);
  const [correctedSql, setCorrectedSql] = useState(sql ?? '');
  const [comment, setComment] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // query_id가 없으면 피드백을 보낼 수 없음
  if (!queryId) return null;

  /** 피드백 전송 */
  const handleSubmit = async (selectedRating: Rating) => {
    if (!selectedRating || submitting) return;
    setSubmitting(true);
    try {
      await oracleApi.post('/feedback', {
        query_id: queryId,
        rating: selectedRating,
        comment: comment || undefined,
        corrected_sql: showCorrection ? correctedSql : undefined,
      });
      setSubmitted(true);
      toast.success('피드백이 저장되었습니다.');
    } catch {
      toast.error('피드백 저장에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="flex items-center gap-2 text-xs text-green-600 font-[IBM_Plex_Mono]">
        <ThumbsUp className="h-3 w-3" />
        피드백이 기록되었습니다
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs text-foreground/60 font-[IBM_Plex_Mono]">결과 평가:</span>
        <Button
          variant="ghost"
          size="icon"
          className={cn('h-7 w-7', rating === 'positive' && 'bg-green-100 text-green-600')}
          onClick={() => {
            setRating('positive');
            handleSubmit('positive');
          }}
          disabled={submitting}
          title="정확한 결과"
        >
          <ThumbsUp className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className={cn('h-7 w-7', rating === 'negative' && 'bg-red-100 text-red-600')}
          onClick={() => {
            setRating('negative');
            handleSubmit('negative');
          }}
          disabled={submitting}
          title="부정확한 결과"
        >
          <ThumbsDown className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className={cn('h-7 text-xs gap-1', showCorrection && 'bg-blue-50 text-blue-600')}
          onClick={() => setShowCorrection(!showCorrection)}
          disabled={submitting}
          title="SQL 수정 제안"
        >
          <Edit3 className="h-3 w-3" />
          수정
        </Button>
      </div>

      {/* SQL 수정 영역 */}
      {showCorrection && (
        <div className="space-y-2 animate-in fade-in slide-in-from-top-1 duration-200">
          <Input
            placeholder="올바른 SQL을 입력하세요..."
            value={correctedSql}
            onChange={(e) => setCorrectedSql(e.target.value)}
            className="text-xs font-[IBM_Plex_Mono] h-8"
          />
          <Input
            placeholder="코멘트 (선택)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="text-xs h-8"
          />
          <Button
            size="sm"
            className="h-7 text-xs"
            onClick={() => {
              setRating('partial');
              handleSubmit('partial');
            }}
            disabled={submitting || !correctedSql.trim()}
          >
            수정 SQL 제출
          </Button>
        </div>
      )}
    </div>
  );
}
