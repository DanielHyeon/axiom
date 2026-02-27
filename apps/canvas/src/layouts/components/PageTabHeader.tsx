import { NavLink } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';
import { UserMenu } from './UserMenu';

const tabs = [
  { to: ROUTES.ANALYSIS.NL2SQL, label: 'NL2SQL' },
  { to: ROUTES.ANALYSIS.OLAP, label: 'OLAP Pivot' },
  { to: ROUTES.ANALYSIS.INSIGHT, label: 'Insight' },
  { to: ROUTES.DATA.ONTOLOGY, label: 'Ontology' },
  { to: ROUTES.DATA.DATASOURCES, label: 'Data' },
];

export function PageTabHeader() {
  return (
    <header className="h-[52px] flex items-center justify-between px-12 border-b border-[#E5E5E5] shrink-0">
      <nav className="flex items-center h-full">
        {tabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              `flex items-center px-4 h-full text-[13px] font-[Sora] transition-colors border-b-2 ${
                isActive
                  ? 'text-black font-semibold border-red-600'
                  : 'text-[#999] border-transparent hover:text-[#666]'
              }`
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>

      <div className="flex items-center gap-3">
        <UserMenu />
      </div>
    </header>
  );
}
