import { NavLink } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';
import { useRole } from '@/shared/hooks/useRole';
import {
  LayoutDashboard,
  MessageSquareText,
  BarChart3,
  Lightbulb,
  Network,
  Database,
  Eye,
  Settings,
} from 'lucide-react';

const navItems = [
  { to: ROUTES.DASHBOARD, icon: LayoutDashboard, label: 'Dashboard' },
  { to: ROUTES.ANALYSIS.NL2SQL, icon: MessageSquareText, label: 'NL2SQL' },
  { to: ROUTES.ANALYSIS.OLAP, icon: BarChart3, label: 'OLAP Pivot' },
  { to: ROUTES.ANALYSIS.INSIGHT, icon: Lightbulb, label: 'Insight' },
  { to: ROUTES.DATA.ONTOLOGY, icon: Network, label: 'Ontology' },
  { to: ROUTES.DATA.DATASOURCES, icon: Database, label: 'Data' },
  { to: ROUTES.WATCH, icon: Eye, label: 'Watch' },
];

export const Sidebar: React.FC = () => {
  const isAdmin = useRole(['admin']);

  return (
    <aside className="w-16 shrink-0 flex flex-col justify-between bg-black">
      {/* Top: Logo + Nav */}
      <div className="flex flex-col items-center pt-8">
        {/* Logo */}
        <div className="flex items-center justify-center w-16 h-16">
          <span className="text-base font-bold text-[#FAFAFA] font-[Sora]">A</span>
        </div>

        {/* Nav items */}
        <nav className="flex flex-col w-full">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              title={item.label}
              className={({ isActive }) =>
                `flex items-center justify-center w-16 h-16 relative group transition-colors ${
                  isActive ? 'text-[#FAFAFA]' : 'text-[#666] hover:text-[#999]'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 bg-red-600 rounded-r" />
                  )}
                  <item.icon className="h-[18px] w-[18px]" />
                  {/* Tooltip */}
                  <div className="absolute left-full ml-2 px-2 py-1 bg-neutral-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-opacity">
                    {item.label}
                  </div>
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* Bottom: Settings */}
      <div className="flex flex-col items-center pb-4">
        {isAdmin && (
          <NavLink
            to={ROUTES.SETTINGS}
            title="Settings"
            className={({ isActive }) =>
              `flex items-center justify-center w-16 h-16 relative group transition-colors ${
                isActive ? 'text-[#FAFAFA]' : 'text-[#666] hover:text-[#999]'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 bg-red-600 rounded-r" />
                )}
                <Settings className="h-[18px] w-[18px]" />
                <div className="absolute left-full ml-2 px-2 py-1 bg-neutral-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 transition-opacity">
                  Settings
                </div>
              </>
            )}
          </NavLink>
        )}
      </div>
    </aside>
  );
};
