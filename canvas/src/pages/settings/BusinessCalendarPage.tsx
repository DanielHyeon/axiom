/**
 * 비즈니스 캘린더 관리 페이지 — 설정 하위.
 * KG-2: 캘린더 선택 + 공휴일 관리 + 영업일 계산.
 */

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { LoadingSpinner } from '@/shared/components/LoadingSpinner';
import { EmptyState } from '@/shared/components/EmptyState';
import { CalendarGrid } from '@/features/calendar/components/CalendarGrid';
import { useCalendars, useCalendar, useAddHoliday, useRemoveHoliday } from '@/features/calendar/hooks/useBusinessCalendar';
import { Calendar, Plus, Trash2 } from 'lucide-react';

export function BusinessCalendarPage() {
  const { data: calendars = [], isLoading } = useCalendars();
  const [selectedId, setSelectedId] = useState<string>('');
  const { data: calendar } = useCalendar(selectedId);
  const addMutation = useAddHoliday(selectedId);
  const removeMutation = useRemoveHoliday(selectedId);

  // 새 공휴일 폼
  const [newName, setNewName] = useState('');
  const [newDate, setNewDate] = useState('');

  const handleAddHoliday = () => {
    if (!newName.trim() || !newDate) return;
    addMutation.mutate({ name: newName.trim(), date: newDate, recurring: false, country: 'KR' });
    setNewName('');
    setNewDate('');
  };

  if (isLoading) return <LoadingSpinner size="lg" label="캘린더 로딩 중" />;

  return (
    <div className="px-4 sm:px-8 lg:px-12 py-4 sm:py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Calendar className="h-6 w-6" /> 비즈니스 캘린더
        </h1>
        <p className="text-sm text-muted-foreground mt-1">공휴일 관리 및 영업일 계산</p>
      </div>

      {/* 캘린더 선택 */}
      {calendars.length === 0 ? (
        <EmptyState title="캘린더가 없습니다" message="시스템 관리자에게 캘린더 생성을 요청하세요" />
      ) : (
        <div className="flex gap-2">
          {calendars.map((c) => (
            <Button
              key={c.id}
              variant={selectedId === c.id ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedId(c.id)}
            >
              {c.name} ({c.country})
            </Button>
          ))}
        </div>
      )}

      {calendar && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 캘린더 그리드 */}
          <CalendarGrid
            holidays={calendar.holidays}
            weekendDays={calendar.weekendDays}
            onDateClick={(date) => setNewDate(date)}
          />

          {/* 공휴일 목록 + 추가 */}
          <div className="space-y-4">
            <div className="border border-border rounded-lg bg-card p-4">
              <h3 className="text-sm font-medium mb-3">공휴일 목록</h3>
              {calendar.holidays.length === 0 ? (
                <p className="text-xs text-muted-foreground">등록된 공휴일이 없습니다</p>
              ) : (
                <div className="space-y-2 max-h-60 overflow-auto">
                  {calendar.holidays.map((h) => (
                    <div key={h.id} className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs text-muted-foreground">{h.date}</span>
                        <span>{h.name}</span>
                        {h.recurring && <Badge variant="outline" className="text-[10px]">매년</Badge>}
                      </div>
                      <button
                        onClick={() => removeMutation.mutate(h.id)}
                        className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                        aria-label={`${h.name} 삭제`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 공휴일 추가 폼 */}
            <div className="border border-border rounded-lg bg-card p-4">
              <h3 className="text-sm font-medium mb-3">공휴일 추가</h3>
              <div className="flex gap-2">
                <Input
                  type="date"
                  value={newDate}
                  onChange={(e) => setNewDate(e.target.value)}
                  className="h-8 text-sm w-40"
                />
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="공휴일 이름"
                  className="h-8 text-sm flex-1"
                />
                <Button size="sm" onClick={handleAddHoliday} disabled={!newName.trim() || !newDate} className="gap-1">
                  <Plus className="h-3.5 w-3.5" /> 추가
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
