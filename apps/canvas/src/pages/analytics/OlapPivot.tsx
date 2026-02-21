import React, { useState } from 'react';

export const OlapPivot: React.FC = () => {
    const [dimensions] = useState(["Region", "Product Category", "Time Segment"]);
    const [metrics] = useState(["Revenue", "COGS", "Margin %"]);
    const [selectedDim, setSelectedDim] = useState("Region");

    return (
        <div className="bg-white rounded shadow p-6 h-full flex flex-col">
            <div className="border-b pb-4 mb-4">
                <h1 className="text-2xl font-bold text-gray-800">Advanced Analytics Pivot</h1>
                <p className="text-gray-500 text-sm">Multidimensional schema exploration powered by Vision.</p>
            </div>

            <div className="flex gap-4 mb-6">
                <div className="flex-1 bg-gray-50 p-4 rounded border">
                    <h3 className="font-semibold text-gray-700 mb-2">Dimensions</h3>
                    <div className="flex flex-wrap gap-2">
                        {dimensions.map(d => (
                            <button
                                key={d}
                                onClick={() => setSelectedDim(d)}
                                className={`px-3 py-1 rounded border text-sm ${selectedDim === d ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-100'}`}
                            >
                                {d}
                            </button>
                        ))}
                    </div>
                </div>
                <div className="flex-1 bg-gray-50 p-4 rounded border">
                    <h3 className="font-semibold text-gray-700 mb-2">Metrics</h3>
                    <div className="flex flex-wrap gap-2">
                        {metrics.map(d => (
                            <span key={d} className="px-3 py-1 rounded border bg-blue-50 text-blue-700 border-blue-200 text-sm">
                                + {d}
                            </span>
                        ))}
                    </div>
                </div>
            </div>

            <div className="flex-1 border rounded bg-gray-50 flex items-center justify-center">
                <p className="text-gray-500 font-medium">Pivot grid rendering for: <span className="text-blue-600">{selectedDim}</span> x All Metrics</p>
            </div>
        </div>
    );
};
