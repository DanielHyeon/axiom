/**
 * DomainModelerLayout — 도메인 모델러 3패널 레이아웃
 *
 * | 좌측 (ObjectTypeTree) | 중앙 (KineticCanvas 플레이스홀더) | 우측 (Editor) |
 *
 * 좌측: ActionType / Policy 트리 뷰
 * 중앙: 향후 Cytoscape 기반 행동 모델 그래프 캔버스 (현재 플레이스홀더)
 * 우측: 선택된 항목의 편집기 (ActionTypeEditor 또는 PolicyEditor)
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { Network } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { ObjectTypeTree } from './ObjectTypeTree';
import { ActionTypeEditor } from './ActionTypeEditor';
import { PolicyEditor } from './PolicyEditor';
import { useActionTypes, usePolicies } from '../hooks/useActionTypes';
import { useDomainModelerStore } from '../store/useDomainModelerStore';

export const DomainModelerLayout: React.FC = () => {
  const { t } = useTranslation();
  const {
    actionTypes,
    selectedActionType,
    loading: loadingAT,
  } = useActionTypes();

  const {
    policies,
    selectedPolicy,
    loading: loadingPol,
  } = usePolicies();

  const editorTarget = useDomainModelerStore((s) => s.editorTarget);

  return (
    <div className="flex h-full gap-2 p-2">
      {/* ── 좌측 패널: 트리 뷰 ── */}
      <Card className="w-64 shrink-0 overflow-hidden flex flex-col">
        <ObjectTypeTree
          actionTypes={actionTypes}
          policies={policies}
          loading={loadingAT || loadingPol}
        />
      </Card>

      {/* ── 중앙 패널: Kinetic Canvas (플레이스홀더) ── */}
      <Card className="flex-1 flex items-center justify-center overflow-hidden">
        <div className="text-center text-muted-foreground space-y-3">
          <Network className="h-16 w-16 mx-auto opacity-30" />
          <div>
            <p className="text-sm font-medium">{t('domainModeler.kineticCanvas')}</p>
            <p className="text-xs mt-1">
              {t('domainModeler.kineticCanvasDesc')}
            </p>
            <p className="text-[11px] mt-2 text-muted-foreground/60">
              {t('domainModeler.kineticCanvasFuture')}
            </p>
          </div>
        </div>
      </Card>

      {/* ── 우측 패널: 에디터 ── */}
      <Card className="w-96 shrink-0 overflow-hidden flex flex-col">
        {editorTarget === 'actionType' ? (
          <ActionTypeEditor actionType={selectedActionType} />
        ) : editorTarget === 'policy' ? (
          <PolicyEditor policy={selectedPolicy} />
        ) : (
          /* 아무것도 선택되지 않은 상태 */
          <div className="flex-1 flex items-center justify-center text-center p-6">
            <div className="text-muted-foreground space-y-2">
              <p className="text-sm">{t('domainModeler.selectItem')}</p>
              <p className="text-xs">
                {t('domainModeler.selectItemDesc')}
              </p>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};
