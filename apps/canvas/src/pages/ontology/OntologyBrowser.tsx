import React from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';

const MOCK_NODES = [
    { id: 'customer-profile', label: 'Customer Profile', className: 'bg-teal-500 border-teal-300', place: 'center' as const },
    { id: 'sales-contract', label: 'Sales Contract', className: 'bg-indigo-500 border-indigo-300', place: 'left' as const },
    { id: 'support-ticket', label: 'Support Ticket', className: 'bg-pink-500 border-pink-300', place: 'right' as const },
];

export const OntologyBrowser: React.FC = () => {
    const [searchParams] = useSearchParams();
    const pathParam = searchParams.get('path') ?? searchParams.get('highlight') ?? '';
    const highlightIds = pathParam ? pathParam.split(',').map((s) => s.trim()).filter(Boolean) : [];

    return (
        <div className="flex flex-col h-full bg-white rounded shadow p-6">
            <div className="border-b pb-4 mb-4 flex justify-between items-start">
                <div>
                    <h1 className="text-2xl font-bold text-gray-800">Ontology Map</h1>
                    <p className="text-gray-500 text-sm">Explore metadata vertices parsed by Synapse and Weaver. URL <code className="text-xs bg-gray-100 px-1">?path=id1,id2</code> 하이라이트.</p>
                </div>
                <Link
                    to={`${ROUTES.PROCESS_DESIGNER.LIST}?fromOntology=${highlightIds[0] ?? 'customer-profile'}`}
                    className="text-sm text-blue-600 hover:underline"
                >
                    프로세스 디자이너에서 보기
                </Link>
            </div>

            <div className="flex-1 bg-slate-900 rounded-lg relative overflow-hidden flex items-center justify-center">
                <div className="absolute inset-0 opacity-20" style={{ backgroundImage: 'radial-gradient(circle at center, #ffffff 1px, transparent 1px)', backgroundSize: '20px 20px' }} />
                <div className="relative text-center">
                    {MOCK_NODES.filter((n) => n.place === 'center').map((node) => {
                        const ring = highlightIds.length > 0 && highlightIds.includes(node.id);
                        return (
                            <div
                                key={node.id}
                                data-path-node={node.id}
                                className={`inline-block text-white font-bold px-6 py-4 rounded-full shadow-lg border-4 mb-8 mx-auto rotate-3 ${node.className} ${ring ? 'ring-4 ring-white ring-offset-2 ring-offset-slate-900' : ''}`}
                            >
                                {node.label}
                            </div>
                        );
                    })}
                    <div className="flex justify-center gap-16">
                        {MOCK_NODES.filter((n) => n.place !== 'center').map((node) => {
                            const ring = highlightIds.length > 0 && highlightIds.includes(node.id);
                            return (
                                <div
                                    key={node.id}
                                    data-path-node={node.id}
                                    className={`${node.className} text-white font-semibold px-4 py-2 rounded shadow-md border-4 ${ring ? 'ring-4 ring-white ring-offset-2 ring-offset-slate-900' : ''}`}
                                >
                                    {node.label}
                                </div>
                            );
                        })}
                    </div>
                    <svg className="absolute top-0 left-0 w-full h-full pointer-events-none" style={{ zIndex: -1 }}>
                        <line x1="50%" y1="35%" x2="35%" y2="65%" stroke="rgba(255,255,255,0.3)" strokeWidth="2" />
                        <line x1="50%" y1="35%" x2="65%" y2="65%" stroke="rgba(255,255,255,0.3)" strokeWidth="2" />
                    </svg>
                </div>
            </div>
        </div>
    );
};
