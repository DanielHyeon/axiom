import { useState, useCallback } from 'react';
import type { Nl2SqlState } from '../types/nl2sql';

const initialState: Nl2SqlState = {
    status: 'idle',
    thinkingText: '',
    sql: null,
    explanation: null,
    columns: [],
    rows: [],
    rowCount: 0,
    queryTime: 0,
    chartRecommendation: null,
};

export function useNl2sqlMock() {
    const [state, setState] = useState<Nl2SqlState>(initialState);

    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const ask = useCallback(async (_: string) => {
        // 1. Start Thinking
        setState({ ...initialState, status: 'thinking', thinkingText: '질문을 분석하고 있습니다...' });

        // 2. Simulate network delay for analyzing
        await new Promise(res => setTimeout(res, 1500));
        setState(prev => ({ ...prev, thinkingText: '관련 테이블을 찾았습니다: financial_statements' }));
        await new Promise(res => setTimeout(res, 1000));

        // 3. Generate SQL
        setState(prev => ({
            ...prev,
            status: 'sql_generated',
            sql: `SELECT company_name,
       total_debt / total_equity AS debt_ratio
FROM financial_statements
WHERE quarter = '2024Q3'
ORDER BY debt_ratio DESC
LIMIT 10;`,
            explanation: '전체 상장사의 재무제표를 바탕으로 2024년 3분기 부채비율 상위 10개 기업을 추출했습니다.',
        }));

        // 4. Simulate user inspecting SQL (Auto execute after 1s for mock)
        await new Promise(res => setTimeout(res, 1500));
        setState(prev => ({ ...prev, status: 'executing' }));

        // 5. Execution delay
        await new Promise(res => setTimeout(res, 1200));

        // 6. Return Mock Data
        setState(prev => ({
            ...prev,
            status: 'result',
            columns: [
                { name: '#', type: 'numeric' },
                { name: '기업명', type: 'varchar' },
                { name: '부채비율', type: 'varchar' }
            ],
            rows: [
                [1, '(주)한진', '482.3%'],
                [2, '두산인프라', '385.1%'],
                [3, '삼성바이오', '312.7%'],
                [4, 'CJ대한통운', '210.5%'],
                [5, 'SK이노베이션', '180.2%'],
            ],
            rowCount: 5,
            queryTime: 1200,
            chartRecommendation: {
                chart_type: 'bar',
                config: {
                    x_column: '기업명',
                    y_column: '부채비율',
                    x_label: 'Company',
                    y_label: 'Debt Ratio (%)'
                }
            }
        }));
    }, []);

    return { state, ask };
}
