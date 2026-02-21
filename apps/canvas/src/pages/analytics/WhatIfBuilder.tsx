import React, { useState } from 'react';
import { apiClient } from '../../lib/api-client';

export const WhatIfBuilder: React.FC = () => {
    const [modifier, setModifier] = useState("");
    const [simulation, setSimulation] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    const handleSimulate = async () => {
        setLoading(true);
        setSimulation(null);
        try {
            const res = await apiClient.post('/vision/analytics/what-if', {
                base_query: "SELECT sum(revenue) FROM sales",
                datasource_id: "ds_1",
                modifications: [{ param: "price_increase", value: modifier }]
            });
            setSimulation(JSON.stringify(res.data, null, 2));
        } catch (err: any) {
            setSimulation(`Simulation Failed: ${err.response?.data?.detail || err.message}`);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="bg-white rounded shadow p-6 h-full">
            <div className="border-b pb-4 mb-6">
                <h1 className="text-2xl font-bold text-gray-800">What-If Scenario Engine</h1>
                <p className="text-gray-500 text-sm">Calculate deep impact regressions securely through Vision.</p>
            </div>

            <div className="max-w-xl">
                <div className="mb-4">
                    <label className="block text-gray-700 font-bold mb-2">Target Metric Modifier</label>
                    <input
                        type="text"
                        placeholder="E.g., +15% Logistics Cost"
                        className="w-full border border-gray-300 rounded p-2 focus:ring-2 focus:ring-indigo-500"
                        value={modifier}
                        onChange={(e) => setModifier(e.target.value)}
                    />
                </div>
                <button
                    onClick={handleSimulate}
                    disabled={loading || !modifier}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-6 rounded disabled:opacity-50"
                >
                    {loading ? "Running Regression..." : "Execute Simulation"}
                </button>
            </div>

            {simulation && (
                <div className="mt-8 p-4 bg-gray-50 border rounded shadow-inner">
                    <h3 className="font-bold text-gray-700 mb-2">Execution Results:</h3>
                    <pre className="text-sm break-words whitespace-pre-wrap">{simulation}</pre>
                </div>
            )}
        </div>
    );
};
