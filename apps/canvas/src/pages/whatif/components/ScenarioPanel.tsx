// src/pages/whatif/components/ScenarioPanel.tsx

import { useWhatIfStore } from '@/features/whatif/store/useWhatIfStore';
import { ParameterSlider } from './ParameterSlider';
import { Button } from '@/components/ui/button';
import { Play, RotateCcw, Save } from 'lucide-react';
import { useWhatIfMock } from '@/features/whatif/hooks/useWhatIfMock';

interface ScenarioPanelProps {
    scenarioId: string;
    onRunAnalysis?: (scenarioId: string) => Promise<void>;
}

export function ScenarioPanel({ scenarioId, onRunAnalysis }: ScenarioPanelProps) {
    const { parameters, scenarios, updateParameter, updateScenarioStatus } = useWhatIfStore();
    const { runAnalysis: mockRunAnalysis } = useWhatIfMock();
    const runAnalysis = onRunAnalysis ?? mockRunAnalysis;

    const scenario = scenarios.find(s => s.id === scenarioId);
    const isComputing = scenario?.status === 'COMPUTING';

    const handleReset = () => {
        parameters.forEach(p => updateParameter(scenarioId, p.id, p.defaultValue));
        updateScenarioStatus(scenarioId, 'DRAFT');
    };

    if (!scenario) return null;

    return (
        <div className="w-80 border-r border-neutral-800 bg-[#161616] flex flex-col h-full">
            <div className="px-5 py-4 border-b border-neutral-800 bg-[#1a1a1a]">
                <h2 className="font-medium text-sm text-neutral-200">매개변수 설정</h2>
                <p className="text-xs text-neutral-500 mt-1">슬라이더를 조정하여 시뮬레이션 하세요.</p>
            </div>

            <div className="p-5 flex-1 overflow-y-auto">
                {parameters.map(p => (
                    <ParameterSlider
                        key={p.id}
                        config={p}
                        value={scenario.parameters[p.id] ?? p.defaultValue}
                        onChange={(val) => updateParameter(scenarioId, p.id, val)}
                        disabled={isComputing}
                    />
                ))}
            </div>

            <div className="p-4 border-t border-neutral-800 bg-[#121212] flex flex-col gap-2">
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" className="flex-1" onClick={handleReset} disabled={isComputing}>
                        <RotateCcw size={14} className="mr-1.5" /> <span>초기화</span>
                    </Button>
                    <Button variant="outline" size="sm" className="flex-1" disabled={isComputing}>
                        <Save size={14} className="mr-1.5" /> <span>저장</span>
                    </Button>
                </div>
                <Button
                    className="w-full bg-indigo-600 hover:bg-indigo-700 font-semibold"
                    onClick={() => runAnalysis(scenarioId)}
                    disabled={isComputing || scenario.status === 'COMPLETED'}
                >
                    <Play size={14} className="mr-1.5" />
                    {isComputing ? '분석 중...' : '분석 실행'}
                </Button>
            </div>
        </div>
    );
}
