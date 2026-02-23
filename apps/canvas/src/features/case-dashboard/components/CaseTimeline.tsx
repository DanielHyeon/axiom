import { Clock } from 'lucide-react';

export interface TimelineItem {
  id: string;
  time: string;
  text: string;
}

export function CaseTimeline({ items = [] }: { items?: TimelineItem[] }) {
  return (
    <div className="glass-card rounded-xl p-5">
      <h3 className="mb-4 text-[13px] font-semibold text-foreground">최근 활동</h3>
      <ul className="space-y-3">
        {items.map((item) => (
          <li key={item.id} className="flex gap-3 text-sm">
            <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10">
              <Clock className="h-3 w-3 text-primary" />
            </div>
            <div>
              <span className="text-foreground">{item.text}</span>
              <p className="text-xs text-muted-foreground">{item.time}</p>
            </div>
          </li>
        ))}
      </ul>
      {items.length === 0 && (
        <div className="flex flex-col items-center py-8 text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-muted/50">
            <Clock className="h-5 w-5 text-muted-foreground/50" />
          </div>
          <p className="text-sm text-muted-foreground">최근 활동이 없습니다.</p>
        </div>
      )}
    </div>
  );
}
