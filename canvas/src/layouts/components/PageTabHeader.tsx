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
 <header className="h-[52px] flex items-center justify-between px-4 pl-14 md:pl-4 md:px-6 lg:px-12 border-b border-border shrink-0">
 <nav className="flex items-center h-full overflow-x-auto scrollbar-none">
 {tabs.map((tab) => (
 <NavLink
 key={tab.to}
 to={tab.to}
 className={({ isActive }) =>
 `flex items-center px-2.5 md:px-4 h-full text-[12px] md:text-[13px] font-heading transition-colors border-b-2 whitespace-nowrap ${
 isActive
 ? 'text-foreground font-semibold border-red-600'
 : 'text-foreground/60 border-transparent hover:text-muted-foreground'
 }`
 }
 >
 {tab.label}
 </NavLink>
 ))}
 </nav>

 <div className="flex items-center gap-2 md:gap-3 shrink-0 ml-2">
 <UserMenu />
 </div>
 </header>
 );
}
