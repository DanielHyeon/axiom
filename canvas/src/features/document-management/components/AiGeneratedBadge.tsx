/**
 * AI 생성 문서 표시 배지.
 * AI가 초안을 생성한 문서임을 시각적으로 알려준다.
 */

import { Badge } from '@/components/ui/badge';

interface AiGeneratedBadgeProps {
  isAiGenerated: boolean;
}

export function AiGeneratedBadge({ isAiGenerated }: AiGeneratedBadgeProps) {
  if (!isAiGenerated) return null;

  return (
    <Badge
      variant="secondary"
      className="text-xs gap-1"
      title="AI가 생성한 문서입니다"
    >
      <span aria-hidden="true">AI</span>
      <span className="sr-only">AI 생성 문서</span>
    </Badge>
  );
}
