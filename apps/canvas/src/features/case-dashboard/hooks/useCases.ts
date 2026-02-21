import { useQuery } from '@tanstack/react-query';

export interface Case {
    id: string;
    title: string;
    status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'REJECTED';
    priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    createdAt: string;
}

const MOCK_CASES: Case[] = [
    {
        id: 'case-001',
        title: '물류최적화 - 현황 분석',
        status: 'IN_PROGRESS',
        priority: 'HIGH',
        createdAt: new Date().toISOString(),
    },
    {
        id: 'case-002',
        title: '신규 공급망 구조 재편',
        status: 'PENDING',
        priority: 'MEDIUM',
        createdAt: new Date(Date.now() - 86400000).toISOString(),
    },
    {
        id: 'case-003',
        title: '2분기 재고 최적화 평가',
        status: 'COMPLETED',
        priority: 'LOW',
        createdAt: new Date(Date.now() - 86400000 * 5).toISOString(),
    }
];

export function useCases() {
    return useQuery({
        queryKey: ['cases'],
        queryFn: async (): Promise<Case[]> => {
            // API 통신을 모방하기 위한 지연
            await new Promise(resolve => setTimeout(resolve, 800));
            return MOCK_CASES;
        },
    });
}
