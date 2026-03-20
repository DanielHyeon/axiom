/**
 * 온톨로지 위자드 UI 상태 스토어 (Zustand)
 * 위자드 모달의 열림/닫힘, 사이드바 표시 등 UI 상태만 관리
 * 비즈니스 로직은 useOntologyWizard 훅에서 담당
 */
import { create } from 'zustand';

interface OntologyWizardUIState {
  // 위자드 모달 열림 상태
  isOpen: boolean;
  openWizard: () => void;
  closeWizard: () => void;

  // 자동 생성 모드 (SchemaBasedGenerator)
  showAutoGenerator: boolean;
  setShowAutoGenerator: (show: boolean) => void;
}

export const useOntologyWizardStore = create<OntologyWizardUIState>((set) => ({
  isOpen: false,
  openWizard: () => set({ isOpen: true }),
  closeWizard: () => set({ isOpen: false, showAutoGenerator: false }),

  showAutoGenerator: false,
  setShowAutoGenerator: (show) => set({ showAutoGenerator: show }),
}));
