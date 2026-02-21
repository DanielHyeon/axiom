import React, { useState } from 'react';

export const DocumentManager: React.FC = () => {
    const [docs] = useState([
        { id: 1, name: "Employee_Handbook_2025.pdf", status: "Extracted", entities: 145 },
        { id: 2, name: "Q4_Financials.docx", status: "Processing", entities: 0 },
        { id: 3, name: "IT_Security_Policy.txt", status: "Failed", entities: 0 },
    ]);

    return (
        <div className="bg-white rounded shadow p-6 h-full">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-800">Document Management</h1>
                    <p className="text-gray-500 text-sm">Upload unstructured files into the Synapse Ontology engine.</p>
                </div>
                <button className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">
                    Upload Document
                </button>
            </div>

            <div className="overflow-x-auto">
                <table className="min-w-full bg-white border border-gray-200">
                    <thead>
                        <tr className="bg-gray-100">
                            <th className="py-2 px-4 border-b text-left text-sm font-semibold text-gray-600">File Name</th>
                            <th className="py-2 px-4 border-b text-left text-sm font-semibold text-gray-600">Status</th>
                            <th className="py-2 px-4 border-b text-left text-sm font-semibold text-gray-600">Entities Found</th>
                            <th className="py-2 px-4 border-b text-left text-sm font-semibold text-gray-600">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {docs.map(doc => (
                            <tr key={doc.id} className="hover:bg-gray-50">
                                <td className="py-3 px-4 border-b text-sm font-medium text-gray-800">{doc.name}</td>
                                <td className="py-3 px-4 border-b text-sm">
                                    <span className={`px-2 py-1 rounded text-xs font-bold ${doc.status === 'Extracted' ? 'bg-green-100 text-green-800' :
                                            doc.status === 'Processing' ? 'bg-yellow-100 text-yellow-800' :
                                                'bg-red-100 text-red-800'
                                        }`}>
                                        {doc.status}
                                    </span>
                                </td>
                                <td className="py-3 px-4 border-b text-sm text-gray-600">{doc.entities || '-'}</td>
                                <td className="py-3 px-4 border-b text-sm">
                                    <button className="text-blue-600 hover:underline mr-3">View</button>
                                    <button className="text-red-600 hover:underline">Delete</button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
