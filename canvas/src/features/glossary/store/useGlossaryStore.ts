/**
 * 글로서리 Zustand 스토어
 * 선택된 용어집, 필터, 편집 대상 등 UI 상태 관리
 */

import { create } from 'zustand';
import type { Glossary, GlossaryTerm, TermStatus } from '../types/glossary';

interface GlossaryState {
  // --- 선택 상태 ---
  /** 현재 선택된 용어집 */
  selectedGlossary: Glossary | null;
  /** 현재 선택된 용어 (상세 보기) */
  selectedTerm: GlossaryTerm | null;

  // --- 필터 ---
  searchQuery: string;
  statusFilter: TermStatus | null;
  categoryFilter: string | null;

  // --- 다이얼로그 제어 ---
  /** 용어 편집 다이얼로그 열림 여부 */
  termEditorOpen: boolean;
  /** 편집 대상 용어 (null이면 신규) */
  editingTerm: GlossaryTerm | null;
  /** 용어집 편집 다이얼로그 열림 여부 */
  glossaryEditorOpen: boolean;
  /** 편집 대상 용어집 (null이면 신규) */
  editingGlossary: Glossary | null;
  /** Import/Export 다이얼로그 */
  importExportOpen: boolean;

  // --- 액션 ---
  setSelectedGlossary: (g: Glossary | null) => void;
  setSelectedTerm: (t: GlossaryTerm | null) => void;
  setSearchQuery: (q: string) => void;
  setStatusFilter: (s: TermStatus | null) => void;
  setCategoryFilter: (c: string | null) => void;

  openTermEditor: (term?: GlossaryTerm | null) => void;
  closeTermEditor: () => void;
  openGlossaryEditor: (glossary?: Glossary | null) => void;
  closeGlossaryEditor: () => void;
  openImportExport: () => void;
  closeImportExport: () => void;

  /** 전체 초기화 */
  reset: () => void;
}

export const useGlossaryStore = create<GlossaryState>((set) => ({
  // 초기값
  selectedGlossary: null,
  selectedTerm: null,
  searchQuery: '',
  statusFilter: null,
  categoryFilter: null,
  termEditorOpen: false,
  editingTerm: null,
  glossaryEditorOpen: false,
  editingGlossary: null,
  importExportOpen: false,

  // 액션
  setSelectedGlossary: (g) => set({ selectedGlossary: g, selectedTerm: null }),
  setSelectedTerm: (t) => set({ selectedTerm: t }),
  setSearchQuery: (q) => set({ searchQuery: q }),
  setStatusFilter: (s) => set({ statusFilter: s }),
  setCategoryFilter: (c) => set({ categoryFilter: c }),

  openTermEditor: (term) =>
    set({ termEditorOpen: true, editingTerm: term ?? null }),
  closeTermEditor: () =>
    set({ termEditorOpen: false, editingTerm: null }),
  openGlossaryEditor: (glossary) =>
    set({ glossaryEditorOpen: true, editingGlossary: glossary ?? null }),
  closeGlossaryEditor: () =>
    set({ glossaryEditorOpen: false, editingGlossary: null }),
  openImportExport: () => set({ importExportOpen: true }),
  closeImportExport: () => set({ importExportOpen: false }),

  reset: () =>
    set({
      selectedGlossary: null,
      selectedTerm: null,
      searchQuery: '',
      statusFilter: null,
      categoryFilter: null,
      termEditorOpen: false,
      editingTerm: null,
      glossaryEditorOpen: false,
      editingGlossary: null,
      importExportOpen: false,
    }),
}));
