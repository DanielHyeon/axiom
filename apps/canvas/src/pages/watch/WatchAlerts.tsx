import React, { useState } from 'react';

export const WatchAlerts: React.FC = () => {
    const [alerts] = useState([
        { id: 'EVT-01', level: 'CRITICAL', message: 'SLA Breach detected on DB sync', time: '2 mins ago' },
        { id: 'EVT-02', level: 'WARNING', message: 'User role escalation anomaly', time: '15 mins ago' },
        { id: 'EVT-03', level: 'INFO', message: 'Graph indexing completed successfully', time: '1 hr ago' },
    ]);

    return (
        <div className="bg-white rounded shadow p-6 h-full">
            <div className="border-b pb-4 mb-6 flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-gray-800">Watch Agent Center</h1>
                    <p className="text-gray-500 text-sm">Real-time complex event processing (CEP) early warnings.</p>
                </div>
                <div className="flex space-x-2">
                    <span className="bg-red-100 text-red-800 text-xs font-bold px-3 py-1 rounded-full animate-pulse">
                        1 Critical
                    </span>
                </div>
            </div>

            <div className="space-y-4">
                {alerts.map(alert => (
                    <div key={alert.id} className={`p-4 border-l-4 rounded bg-gray-50 shadow-sm flex flex-col ${alert.level === 'CRITICAL' ? 'border-red-500' :
                            alert.level === 'WARNING' ? 'border-yellow-500' : 'border-blue-500'
                        }`}>
                        <div className="flex justify-between items-center mb-1">
                            <span className={`text-xs font-bold uppercase ${alert.level === 'CRITICAL' ? 'text-red-700' :
                                    alert.level === 'WARNING' ? 'text-yellow-700' : 'text-blue-700'
                                }`}>
                                {alert.level} | {alert.id}
                            </span>
                            <span className="text-xs text-gray-500">{alert.time}</span>
                        </div>
                        <p className="text-gray-800 font-medium">{alert.message}</p>
                    </div>
                ))}
            </div>
        </div>
    );
};
