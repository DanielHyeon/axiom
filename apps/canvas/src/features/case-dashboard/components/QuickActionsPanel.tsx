import { Link } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';

const ACTIONS = [
  { label: '케이스 목록', to: ROUTES.CASES.LIST },
  { label: 'NL2SQL', to: ROUTES.ANALYSIS.NL2SQL },
  { label: 'OLAP 피벗', to: ROUTES.ANALYSIS.OLAP },
];

export function QuickActionsPanel() {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
      <h3 className="mb-3 text-sm font-semibold text-white">바로가기</h3>
      <div className="flex flex-wrap gap-2">
        {ACTIONS.map((a) => (
          <Link
            key={a.to}
            to={a.to}
            className="rounded bg-neutral-800 px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-700"
          >
            {a.label}
          </Link>
        ))}
      </div>
    </div>
  );
}
