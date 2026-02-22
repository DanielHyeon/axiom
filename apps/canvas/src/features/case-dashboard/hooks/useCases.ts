import { useQuery } from '@tanstack/react-query';

export interface Case {
    id: string;
    title: string;
    status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'REJECTED';
    priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    createdAt: string;
    /** 마감일 (YYYY-MM-DD). 이번주 마감 통계용 */
    dueDate?: string;
}

const MOCK_CASES: Case[] = [
    {
        id: 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d',
        title: '물류최적화 - 현황 분석',
        status: 'IN_PROGRESS',
        priority: 'HIGH',
        createdAt: new Date().toISOString(),
        dueDate: new Date(Date.now() + 86400000 * 3).toISOString().slice(0, 10),
    },
    {
        id: 'b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e',
        title: '신규 공급망 구조 재편',
        status: 'PENDING',
        priority: 'MEDIUM',
        createdAt: new Date(Date.now() - 86400000).toISOString(),
        dueDate: new Date(Date.now() + 86400000 * 5).toISOString().slice(0, 10),
    },
    {
        id: 'c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f',
        title: '2분기 재고 최적화 평가',
        status: 'COMPLETED',
        priority: 'LOW',
        createdAt: new Date(Date.now() - 86400000 * 5).toISOString(),
    },
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
