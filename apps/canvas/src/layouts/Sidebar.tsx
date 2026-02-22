import React from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';

export const Sidebar: React.FC = () => (
  <aside className="w-64 bg-white shadow-md flex flex-col shrink-0">
    <div className="p-4 border-b">
      <h1 className="text-xl font-bold text-blue-600">Axiom Canvas</h1>
    </div>
    <nav className="flex-1 p-4 space-y-2">
      <Link to={ROUTES.DASHBOARD} className="block p-2 rounded hover:bg-gray-100 text-gray-700">
        📊 Dashboard
      </Link>
      <Link to={ROUTES.CASES.LIST} className="block p-2 rounded hover:bg-gray-100 text-gray-700">
        📁 케이스
      </Link>
      <hr className="my-2 border-gray-200" />
      <Link to={ROUTES.ANALYSIS.NL2SQL} className="block p-2 rounded hover:bg-gray-100 text-gray-700">
        💬 NL-to-SQL
      </Link>
      <Link to={ROUTES.ANALYSIS.OLAP} className="block p-2 rounded hover:bg-gray-100 text-gray-700">
        📈 OLAP Pivot
      </Link>
      <hr className="my-2 border-gray-200" />
      <Link to={ROUTES.DATA.ONTOLOGY} className="block p-2 rounded hover:bg-gray-100 text-gray-700">
        🕸️ Ontology
      </Link>
      <Link to={ROUTES.DATA.DATASOURCES} className="block p-2 rounded hover:bg-gray-100 text-gray-700">
        🔌 데이터소스
      </Link>
      <Link to={ROUTES.PROCESS_DESIGNER.LIST} className="block p-2 rounded hover:bg-gray-100 text-gray-700">
        ⚙️ Process Designer
      </Link>
      <Link to={ROUTES.WATCH} className="block p-2 rounded hover:bg-gray-100 text-gray-700">
        🚨 Watch Alerts
      </Link>
      <Link to={ROUTES.SETTINGS} className="block p-2 rounded hover:bg-gray-100 text-gray-700">
        ⚙ 설정
      </Link>
    </nav>
  </aside>
);
