import { NavLink } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';
import { UserMenu } from './UserMenu';

/** 상단 탭 네비게이션 — 디자인 사양: 52px 높이, Sora 13px */
const tabs = [
  { to: ROUTES.ANALYSIS.NL2SQL, label: 'NL2SQL' },
  { to: ROUTES.ANALYSIS.OLAP, label: 'OLAP Pivot' },
  { to: ROUTES.ANALYSIS.INSIGHT, label: 'Insight' },
  { to: ROUTES.DATA.ONTOLOGY, label: 'Ontology' },
  { to: ROUTES.DATA.DATASOURCES, label: 'Data' },
];

export function PageTabHeader() {
  return (
    <header className="h-[52px] flex items-center justify-between px-12 border-b border-border shrink-0">
      {/* 왼쪽: 탭 네비게이션 — 모바일에서 가로 스크롤 허용 */}
      <nav className="flex items-center h-full overflow-x-auto scrollbar-none">
        {tabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              [
                'flex items-center h-full py-2.5 px-4 font-heading text-[13px] whitespace-nowrap transition-colors border-b-2',
                isActive
                  ? 'text-foreground font-semibold border-primary'
                  : 'text-muted-foreground/60 font-normal border-transparent hover:text-muted-foreground',
              ].join(' ')
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>

      {/* 오른쪽: 사용자 아바타 */}
      <div className="shrink-0 ml-2">
        <UserMenu />
      </div>
    </header>
  );
}
