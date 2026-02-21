import React from 'react';

export const OntologyBrowser: React.FC = () => {
    return (
        <div className="flex flex-col h-full bg-white rounded shadow p-6">
            <div className="border-b pb-4 mb-4">
                <h1 className="text-2xl font-bold text-gray-800">Ontology Map</h1>
                <p className="text-gray-500 text-sm">Explore metadata vertices parsed by Synapse and Weaver.</p>
            </div>

            <div className="flex-1 bg-slate-900 rounded-lg relative overflow-hidden flex items-center justify-center">
                {/* Mocking a D3/Vis.js graph visualization placeholder */}
                <div className="absolute inset-0 opacity-20" style={{ backgroundImage: 'radial-gradient(circle at center, #ffffff 1px, transparent 1px)', backgroundSize: '20px 20px' }}></div>

                <div className="relative text-center">
                    <div className="inline-block bg-teal-500 text-white font-bold px-6 py-4 rounded-full shadow-lg border-4 border-teal-300 mb-8 mx-auto rotate-3">
                        Customer Profile
                    </div>

                    <div className="flex justify-center gap-16">
                        <div className="bg-indigo-500 text-white font-semibold px-4 py-2 rounded shadow-md">
                            Sales Contract
                        </div>
                        <div className="bg-pink-500 text-white font-semibold px-4 py-2 rounded shadow-md">
                            Support Ticket
                        </div>
                    </div>

                    {/* Mock edges */}
                    <svg className="absolute top-0 left-0 w-full h-full pointer-events-none" style={{ zIndex: -1 }}>
                        <line x1="50%" y1="35%" x2="35%" y2="65%" stroke="rgba(255,255,255,0.3)" strokeWidth="2" />
                        <line x1="50%" y1="35%" x2="65%" y2="65%" stroke="rgba(255,255,255,0.3)" strokeWidth="2" />
                    </svg>
                </div>
            </div>
        </div>
    );
};
