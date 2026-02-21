// src/pages/whatif/components/ParameterSlider.tsx

import type { ParameterConfig } from '@/features/whatif/types/whatif';
import { Slider } from '@/components/ui/slider';

interface ParameterSliderProps {
    config: ParameterConfig;
    value: number;
    onChange: (value: number) => void;
    disabled?: boolean;
}

export function ParameterSlider({ config, value, onChange, disabled }: ParameterSliderProps) {
    return (
        <div className="mb-6 last:mb-0">
            <div className="flex justify-between items-center mb-2">
                <label className="text-sm font-medium text-neutral-300">{config.name}</label>
                <span className="text-sm font-semibold text-indigo-400 bg-indigo-950/50 px-2 py-0.5 rounded">
                    {value}{config.unit}
                </span>
            </div>
            <Slider
                value={[value]}
                min={config.min}
                max={config.max}
                step={config.step}
                onValueChange={(vals: number[]) => onChange(vals[0])}
                disabled={disabled}
                className="my-4"
            />
            <div className="flex justify-between text-xs text-neutral-500">
                <span>{config.min}{config.unit}</span>
                <span>{config.max}{config.unit}</span>
            </div>
        </div>
    );
}
