/**
 * Vision What-if 위자드 API — shared re-export
 *
 * 실제 구현은 features/whatif/api/visionWizardApi.ts에 있다.
 * whatif-wizard 등 다른 feature에서 직접 whatif를 참조하지 않도록
 * shared 레이어를 통해 접근한다.
 */

export {
  discoverEdges,
  buildModelGraph,
  trainModels,
  listModels,
  getSnapshot,
  runSimulation,
} from '@/features/whatif/api/visionWizardApi';
