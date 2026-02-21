import React, { useState } from 'react';

export const ProcessDesigner: React.FC = () => {
    const [nodes, setNodes] = useState([
        { id: '1', label: 'Start Process' },
        { id: '2', label: 'Approval Required' }
    ]);

    return (
        <div className="flex flex-col h-full bg-white rounded shadow p-6">
            <div className="border-b pb-4 mb-4">
                <h1 className="text-2xl font-bold text-gray-800">Process Designer</h1>
                <p className="text-gray-500 text-sm">Visualize and construct your Synapse business process maps.</p>
            </div>

            <div className="flex-1 bg-gray-50 border-2 border-dashed border-gray-300 rounded flex items-center justify-center relative p-8">
                {/* Mocking a canvas workspace */}
                <div className="flex space-x-8 items-center">
                    {nodes.map((n, i) => (
                        <React.Fragment key={n.id}>
                            <div className="p-4 bg-white border border-blue-500 rounded shadow-sm flex items-center justify-center font-medium text-blue-700">
                                {n.label}
                            </div>
                            {i < nodes.length - 1 && (
                                <div className="h-1 w-12 bg-blue-300"></div>
                            )}
                        </React.Fragment>
                    ))}
                    <button
                        onClick={() => setNodes([...nodes, { id: Date.now().toString(), label: "New Step" }])}
                        className="p-4 rounded-full bg-blue-100 text-blue-600 hover:bg-blue-200 border border-blue-300 font-bold shadow-sm"
                    >
                        + Add Node
                    </button>
                </div>
            </div>
        </div>
    );
};
