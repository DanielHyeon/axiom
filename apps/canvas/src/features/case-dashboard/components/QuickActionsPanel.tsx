import { Link } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';
import { List, MessageSquare, BarChart3 } from 'lucide-react';

const ACTIONS = [
  { label: '케이스 목록', to: ROUTES.CASES.LIST, icon: List },
  { label: 'NL2SQL', to: ROUTES.ANALYSIS.NL2SQL, icon: MessageSquare },
  { label: 'OLAP 피벗', to: ROUTES.ANALYSIS.OLAP, icon: BarChart3 },
];

export function QuickActionsPanel() {
  return (
    <div className="glass-card rounded-xl p-5">
      <h3 className="mb-3 text-[13px] font-semibold text-foreground">바로가기</h3>
      <div className="flex flex-wrap gap-2">
        {ACTIONS.map((a) => (
          <Link
            key={a.to}
            to={a.to}
            className="inline-flex items-center gap-2 rounded-lg bg-muted/40 border border-border/30 px-4 py-2.5 text-[13px] font-medium text-foreground transition-all duration-200 hover:bg-primary/10 hover:text-primary"
          >
            <a.icon className="h-4 w-4 text-primary/70" />
            {a.label}
          </Link>
        ))}
      </div>
    </div>
  );
}
