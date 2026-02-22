import { useSearchParams } from 'react-router-dom';
import { usePivotConfig } from '../store/usePivotConfig';
import { useMemo, useEffect } from 'react';

const DRILL_PARAM = 'drill';

/** 드릴다운 경로 표시 및 URL search params 동기화 */
export function DrilldownBreadcrumb() {
  const [searchParams] = useSearchParams();
  const drilldownPath = usePivotConfig((s) => s.drilldownPath);
  const setDrilldownPath = usePivotConfig((s) => s.setDrilldownPath);

  const pathFromUrl = useMemo(() => {
    const raw = searchParams.get(DRILL_PARAM);
    if (!raw) return [];
    return raw.split('|').map((segment) => {
      const [dimensionId, value] = segment.split(':');
      return { dimensionId: dimensionId ?? '', value: decodeURIComponent(value ?? '') };
    });
  }, [searchParams]);

  useEffect(() => {
    if (pathFromUrl.length > 0) {
      setDrilldownPath(pathFromUrl.map((p) => ({ dimensionId: p.dimensionId, value: p.value })));
    }
  }, [searchParams.get(DRILL_PARAM)]);

  if (drilldownPath.length === 0 && pathFromUrl.length === 0) return null;

  const displayPath = drilldownPath.length > 0 ? drilldownPath : pathFromUrl;

  return (
    <div className="flex items-center gap-2 text-sm text-neutral-400 flex-wrap">
      <span>드릴다운:</span>
      {displayPath.map((step, i) => (
        <span key={i} className="flex items-center gap-2">
          {i > 0 && <span className="text-neutral-600">/</span>}
          <span className="rounded bg-neutral-800 px-2 py-0.5 text-neutral-300">
            {step.dimensionId} = {step.value}
          </span>
        </span>
      ))}
    </div>
  );
}
