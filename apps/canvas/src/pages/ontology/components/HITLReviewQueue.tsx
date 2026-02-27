import { useState, useEffect, useCallback } from 'react';
import { getHITLItems, approveHITL, rejectHITL } from '@/features/ontology/api/ontologyApi';
import type { HITLItem } from '@/features/ontology/types/ontology';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  CheckCircle,
  XCircle,
  MessageSquare,
  Clock,
  X,
  Loader2,
  ChevronDown,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface HITLReviewQueueProps {
  caseId: string;
  onClose: () => void;
}

const LAYER_BADGE: Record<string, string> = {
  kpi: 'border-violet-300 text-violet-600',
  measure: 'border-blue-300 text-blue-600',
  process: 'border-emerald-300 text-emerald-600',
  resource: 'border-amber-300 text-amber-600',
};

export function HITLReviewQueue({ caseId, onClose }: HITLReviewQueueProps) {
  const [items, setItems] = useState<HITLItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actioningId, setActioningId] = useState<string | null>(null);
  const [commentId, setCommentId] = useState<string | null>(null);
  const [comment, setComment] = useState('');
  const [offset, setOffset] = useState(0);
  const LIMIT = 20;

  const fetchItems = useCallback(
    async (newOffset = 0) => {
      setLoading(true);
      setError(null);
      try {
        const data = await getHITLItems(caseId, 'pending', LIMIT, newOffset);
        if (newOffset === 0) {
          setItems(data.items);
        } else {
          setItems((prev) => [...prev, ...data.items]);
        }
        setTotal(data.pagination.total);
        setOffset(newOffset);
      } catch (err) {
        setError((err as Error).message || 'Failed to load review queue');
      } finally {
        setLoading(false);
      }
    },
    [caseId],
  );

  useEffect(() => {
    fetchItems(0);
  }, [fetchItems]);

  const handleApprove = async (itemId: string) => {
    setActioningId(itemId);
    try {
      await approveHITL(itemId, commentId === itemId ? comment : '');
      setItems((prev) => prev.filter((i) => i.id !== itemId));
      setTotal((prev) => prev - 1);
      if (commentId === itemId) {
        setCommentId(null);
        setComment('');
      }
    } catch (err) {
      setError((err as Error).message || 'Approve failed');
    } finally {
      setActioningId(null);
    }
  };

  const handleReject = async (itemId: string) => {
    setActioningId(itemId);
    try {
      await rejectHITL(itemId, commentId === itemId ? comment : '');
      setItems((prev) => prev.filter((i) => i.id !== itemId));
      setTotal((prev) => prev - 1);
      if (commentId === itemId) {
        setCommentId(null);
        setComment('');
      }
    } catch (err) {
      setError((err as Error).message || 'Reject failed');
    } finally {
      setActioningId(null);
    }
  };

  const hasMore = items.length < total;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between h-[52px] px-6 border-b border-[#E5E5E5] shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-semibold text-black font-[Sora]">검토 대기열</span>
          <Badge variant="outline" className="text-[10px] border-[#E5E5E5] tabular-nums font-[IBM_Plex_Mono]">
            {total}
          </Badge>
        </div>
        <button type="button" onClick={onClose} className="text-[#999] hover:text-black text-lg transition-colors">
          ×
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {loading && items.length === 0 && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-[#999]" />
          </div>
        )}

        {error && (
          <div className="m-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-600">
            {error}
          </div>
        )}

        {!loading && items.length === 0 && !error && (
          <div className="flex flex-col items-center justify-center py-8 text-[#999] gap-1">
            <CheckCircle className="h-6 w-6 opacity-40" />
            <span className="text-xs font-[IBM_Plex_Mono]">검토 대기 항목이 없습니다</span>
          </div>
        )}

        <div className="divide-y divide-[#E5E5E5]">
          {items.map((item) => {
            const isActioning = actioningId === item.id;
            const showComment = commentId === item.id;
            return (
              <div key={item.id} className="p-4 space-y-2">
                {/* Item header */}
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] text-black truncate font-[Sora]">
                      {item.node_name || item.node_id}
                    </div>
                    <div className="flex items-center gap-1.5 mt-1">
                      {item.node_layer && (
                        <Badge
                          variant="outline"
                          className={cn(
                            'text-[10px] capitalize font-[IBM_Plex_Mono]',
                            LAYER_BADGE[item.node_layer] ?? 'border-[#E5E5E5] text-[#999]',
                          )}
                        >
                          {item.node_layer}
                        </Badge>
                      )}
                      <span className="text-[10px] text-[#999] flex items-center gap-0.5 font-[IBM_Plex_Mono]">
                        <Clock className="h-2.5 w-2.5" />
                        {new Date(item.submitted_at).toLocaleDateString('ko-KR')}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Comment toggle */}
                {showComment && (
                  <textarea
                    className="w-full h-16 rounded border border-[#E5E5E5] bg-white p-2 text-xs text-black font-[IBM_Plex_Mono] resize-none focus:outline-none focus:border-[#999]"
                    placeholder="검토 코멘트 (선택)"
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                  />
                )}

                {/* Actions */}
                <div className="flex items-center gap-1.5">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-green-600 hover:text-green-700 hover:bg-green-50"
                    disabled={isActioning}
                    onClick={() => handleApprove(item.id)}
                  >
                    {isActioning ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <CheckCircle className="h-3.5 w-3.5" />
                    )}
                    <span className="ml-1 text-xs font-[Sora]">승인</span>
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-red-500 hover:text-red-600 hover:bg-red-50"
                    disabled={isActioning}
                    onClick={() => handleReject(item.id)}
                  >
                    <XCircle className="h-3.5 w-3.5" />
                    <span className="ml-1 text-xs font-[Sora]">반려</span>
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 ml-auto"
                    onClick={() => {
                      if (showComment) {
                        setCommentId(null);
                        setComment('');
                      } else {
                        setCommentId(item.id);
                        setComment('');
                      }
                    }}
                  >
                    <MessageSquare
                      className={cn('h-3.5 w-3.5', showComment ? 'text-blue-500' : 'text-[#999]')}
                    />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Load more */}
        {hasMore && (
          <div className="p-3">
            <Button
              variant="ghost"
              size="sm"
              className="w-full h-8 text-xs text-[#999] font-[Sora]"
              disabled={loading}
              onClick={() => fetchItems(offset + LIMIT)}
            >
              {loading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5 mr-1" />
              )}
              더 보기 ({items.length}/{total})
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
