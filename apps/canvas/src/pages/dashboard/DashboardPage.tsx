import React, { useEffect, useState } from 'react';
import { apiClient } from '../../lib/api-client';

export const DashboardPage: React.FC = () => {
    const [data, setData] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchDashboard = async () => {
            try {
                // Integrating Vision Analytic stubs
                const res = await apiClient.post('/vision/analytics/execute', { query: 'SELECT 1', datasource_id: 'ds_1' });
                setData(res.data);
            } catch (err) {
                console.error("Dashboard Load Error", err);
            } finally {
                setLoading(false);
            }
        };
        fetchDashboard();
    }, []);

    return (
        <div>
            <h1 className="text-2xl font-bold mb-4">Enterprise Operations Dashboard</h1>
            {loading ? (
                <p className="text-gray-500 animate-pulse">Loading analytics...</p>
            ) : (
                <div className="bg-white p-6 rounded shadow">
                    <h2 className="text-lg font-semibold mb-2">Metrics Loaded Successfully</h2>
                    <pre className="text-sm bg-gray-50 p-4 rounded overflow-auto">
                        {JSON.stringify(data, null, 2)}
                    </pre>
                </div>
            )}
        </div>
    );
};
