
interface TimelineItem {
  id: string;
  time: string;
  text: string;
}

const MOCK_TIMELINE: TimelineItem[] = [
  { id: '1', time: '14:30', text: '문서 승인' },
  { id: '2', time: '13:15', text: '케이스 생성' },
  { id: '3', time: '11:00', text: '리뷰 완료' },
];

export function CaseTimeline({ items = MOCK_TIMELINE }: { items?: TimelineItem[] }) {
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
    </div>
  );
}
