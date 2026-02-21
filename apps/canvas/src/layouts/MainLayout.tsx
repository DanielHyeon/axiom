import React from 'react';
import { Outlet, Link } from 'react-router-dom';

export const MainLayout: React.FC = () => {
    return (
        <div className="flex h-screen bg-gray-50">
            {/* Sidebar Navigation */}
            <aside className="w-64 bg-white shadow-md flex flex-col">
                <div className="p-4 border-b">
                    <h1 className="text-xl font-bold text-blue-600">Axiom Canvas</h1>
                </div>
                <nav className="flex-1 p-4 space-y-2">
                    <Link to="/" className="block p-2 rounded hover:bg-gray-100 text-gray-700">
                        📊 Dashboard
                    </Link>
                    <Link to="/nl2sql" className="block p-2 rounded hover:bg-gray-100 text-gray-700">
                        💬 NL-to-SQL
                    </Link>
                    <Link to="/process" className="block p-2 rounded hover:bg-gray-100 text-gray-700">
                        ⚙️ Process Map
                    </Link>
                    <Link to="/documents" className="block p-2 rounded hover:bg-gray-100 text-gray-700">
                        📁 Documents
                    </Link>
                    <hr className="my-2 border-gray-200" />
                    <Link to="/analytics/pivot" className="block p-2 rounded hover:bg-gray-100 text-gray-700">
                        📈 OLAP Pivot
                    </Link>
                    <Link to="/analytics/what-if" className="block p-2 rounded hover:bg-gray-100 text-gray-700">
                        🎯 What-If Builder
                    </Link>
                    <hr className="my-2 border-gray-200" />
                    <Link to="/ontology" className="block p-2 rounded hover:bg-gray-100 text-gray-700">
                        🕸️ Ontology Map
                    </Link>
                    <Link to="/watch" className="block p-2 rounded hover:bg-gray-100 text-gray-700">
                        🚨 Watch Alerts
                    </Link>
                </nav>
            </aside>

            {/* Main Content Area */}
            <main className="flex-1 p-8 overflow-auto">
                <Outlet />
            </main>
        </div>
    );
};
