/**
 * Vision 서비스 What-if 위자드 API — 배럴(barrel) re-export
 *
 * 기존 코드에서 `import * as wizardApi from '.../visionWizardApi'` 형태로
 * 사용하던 코드가 깨지지 않도록, 분리된 모듈들을 모두 re-export한다.
 *
 * 새 코드에서는 각 모듈을 직접 import하는 것을 권장:
 *   - discoveryApi.ts  — 인과 분석 관련 (discoverEdges, buildModelGraph)
 *   - trainingApi.ts   — 모델 학습 관련 (trainModels, listModels)
 *   - simulationApi.ts — 시뮬레이션 관련 (getSnapshot, runSimulation)
 *   - types.ts         — API 응답 타입 + 변환 헬퍼
 *   - mockData.ts      — 백엔드 미구현 시 사용하는 mock 데이터
 */

// 인과 분석 API
export { discoverEdges, buildModelGraph } from './discoveryApi';

// 모델 학습 API
export { trainModels, listModels } from './trainingApi';

// 시뮬레이션 API
export { getSnapshot, runSimulation } from './simulationApi';
