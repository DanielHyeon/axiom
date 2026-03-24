// src/pages/whatif/components/ScenarioPanel.tsx

import { useWhatIfStore } from '@/features/whatif/store/useWhatIfStore';
import { ParameterSlider } from './ParameterSlider';
import { Button } from '@/components/ui/button';
import { Play, RotateCcw, Save } from 'lucide-react';
import { useWhatIfMock } from '@/features/whatif/hooks/useWhatIfMock';
import { useTranslation } from 'react-i18next';

interface ScenarioPanelProps {
 scenarioId: string;
 onRunAnalysis?: (scenarioId: string) => Promise<void>;
}

export function ScenarioPanel({
  const { t } = useTranslation(); scenarioId, onRunAnalysis }: ScenarioPanelProps) {
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
 <div className="w-80 border-r border-border bg-popover flex flex-col h-full">
 <div className="px-5 py-4 border-b border-border bg-popover">
 <h2 className="font-medium text-sm text-foreground">{t('whatifPage.msge8fbd141')}</h2>
 <p className="text-xs text-foreground0 mt-1">{t('whatifPage.msg928a478b')}</p>
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

 <div className="p-4 border-t border-border bg-background flex flex-col gap-2">
 <div className="flex gap-2">
 <Button variant="outline" size="sm" className="flex-1" onClick={handleReset} disabled={isComputing}>
 <RotateCcw size={14} className="mr-1.5" /> <span>{t('objectExplorerExt.reset')}</span>
 </Button>
 <Button variant="outline" size="sm" className="flex-1" disabled={isComputing}>
 <Save size={14} className="mr-1.5" /> <span>{t('domainModeler.save')}</span>
 </Button>
 </div>
 <Button
 className="w-full bg-primary hover:bg-primary/90 font-semibold"
 onClick={() => runAnalysis(scenarioId)}
 disabled={isComputing || scenario.status === 'COMPLETED'}
 >
 <Play size={14} className="mr-1.5" />
 {isComputing ? t('whatifExt.edgeDiscovery.analyzing') : t('whatifPage.mb37ad511')}
 </Button>
 </div>
 </div>
 );
}
