export interface TimelineItem {
  id: string;
  time: string;
  text: string;
}

export function CaseTimeline({ items = [] }: { items?: TimelineItem[] }) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
      <h3 className="mb-3 text-sm font-semibold text-white">최근 활동</h3>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.id} className="flex gap-2 text-sm">
            <span className="text-neutral-500">{item.time}</span>
            <span className="text-neutral-300">{item.text}</span>
          </li>
        ))}
      </ul>
      {items.length === 0 && (
        <p className="text-sm text-neutral-500">최근 활동이 없습니다.</p>
      )}
    </div>
  );
}
