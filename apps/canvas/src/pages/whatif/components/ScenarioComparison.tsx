import React from 'react';

export interface ScenarioComparisonRow {
  scenario_id: string;
  scenario_name: string;
  npv_at_wacc?: number | null;
  feasibility_score?: number | null;
}

interface ScenarioComparisonProps {
  items: ScenarioComparisonRow[];
}

/** 복수 시나리오 열 비교 테이블. NPV·실현가능성 등 지표를 시나리오별로 나란히 표시. */
export function ScenarioComparison({ items }: ScenarioComparisonProps) {
  if (items.length === 0) return null;

  return (
    <div className="mb-6 border border-neutral-800 rounded-lg overflow-hidden">
      <table className="w-full text-sm text-left">
        <thead className="bg-neutral-800 text-neutral-300">
          <tr>
            <th className="p-3">시나리오</th>
            <th className="p-3">NPV (WACC)</th>
            <th className="p-3">실현가능성</th>
          </tr>
        </thead>
        <tbody className="bg-neutral-900 text-neutral-200">
          {items.map((row) => (
            <tr key={row.scenario_id} className="border-t border-neutral-800">
              <td className="p-3">{row.scenario_name}</td>
              <td className="p-3">
                {row.npv_at_wacc != null ? Number(row.npv_at_wacc).toLocaleString() : '-'}
              </td>
              <td className="p-3">
                {row.feasibility_score != null ? Number(row.feasibility_score) : '-'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
