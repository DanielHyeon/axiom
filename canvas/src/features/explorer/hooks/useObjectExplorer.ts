/**
 * useObjectExplorer — 오브젝트 탐색 드릴다운 훅
 *
 * 검색 → 결과 선택 → 자식 드릴다운 → 브레드크럼 내비게이션을
 * 하나의 훅으로 통합 관리한다.
 *
 * 반환값:
 *   - search(query)     : 키워드 검색 실행
 *   - drillDown(item)   : 선택한 항목의 자식으로 드릴다운
 *   - goBack(index)     : 브레드크럼 특정 위치로 복귀
 *   - selectItem(item)  : 속성 패널에 표시할 항목 선택
 *   - results           : 현재 표시 중인 결과 목록
 *   - children          : 드릴다운 결과 (그룹별)
 *   - breadcrumb        : 네비게이션 경로
 *   - selectedItem      : 현재 선택된 항목
 *   - isSearching       : 검색 로딩 상태
 *   - isDrilling        : 드릴다운 로딩 상태
 *   - error             : 에러 메시지
 */

import { useState, useCallback } from 'react';
import { toast } from 'sonner';
import { searchObjects, getChildren } from '../api/explorerApi';
import type {
  ObjectSearchResult,
  ChildGroup,
  BreadcrumbItem,
} from '../types/explorer';

// ──────────────────────────────────────
// 훅 반환 타입
// ──────────────────────────────────────

interface UseObjectExplorerReturn {
  /** 키워드 검색 실행 */
  search: (query: string) => Promise<void>;
  /** 선택한 항목의 자식으로 드릴다운 */
  drillDown: (item: ObjectSearchResult) => Promise<void>;
  /** 브레드크럼 특정 위치로 복귀 (인덱스 기반) */
  goBack: (index: number) => void;
  /** 속성 패널에 표시할 항목 선택 */
  selectItem: (item: ObjectSearchResult | null) => void;
  /** 현재 표시 중인 검색 결과 */
  results: ObjectSearchResult[];
  /** 드릴다운 결과 (오브젝트 유형별 그룹) */
  children: ChildGroup[];
  /** 네비게이션 경로 */
  breadcrumb: BreadcrumbItem[];
  /** 현재 선택된 항목 (상세 패널용) */
  selectedItem: ObjectSearchResult | null;
  /** 검색 로딩 상태 */
  isSearching: boolean;
  /** 드릴다운 로딩 상태 */
  isDrilling: boolean;
  /** 에러 메시지 */
  error: string | null;
  /** 현재 검색어 */
  searchQuery: string;
  /** 전체 상태 초기화 */
  reset: () => void;
}

// ──────────────────────────────────────
// 훅 구현
// ──────────────────────────────────────

export function useObjectExplorer(): UseObjectExplorerReturn {
  // 검색 결과
  const [results, setResults] = useState<ObjectSearchResult[]>([]);
  // 드릴다운 자식 그룹
  const [children, setChildren] = useState<ChildGroup[]>([]);
  // 브레드크럼 경로
  const [breadcrumb, setBreadcrumb] = useState<BreadcrumbItem[]>([]);
  // 선택된 항목 (상세 표시용)
  const [selectedItem, setSelectedItem] = useState<ObjectSearchResult | null>(null);
  // 로딩 상태
  const [isSearching, setIsSearching] = useState(false);
  const [isDrilling, setIsDrilling] = useState(false);
  // 에러
  const [error, setError] = useState<string | null>(null);
  // 현재 검색어
  const [searchQuery, setSearchQuery] = useState('');

  // 드릴다운 이력 (goBack 시 이전 결과를 복원하기 위한 스냅샷)
  const [history, setHistory] = useState<
    Array<{
      results: ObjectSearchResult[];
      children: ChildGroup[];
    }>
  >([]);

  /** 키워드 검색 실행 */
  const search = useCallback(async (query: string) => {
    // 빈 검색어 무시
    if (!query.trim()) return;

    setIsSearching(true);
    setError(null);
    // 검색 시 드릴다운 상태 초기화
    setBreadcrumb([]);
    setChildren([]);
    setSelectedItem(null);
    setHistory([]);
    setSearchQuery(query.trim());

    try {
      const res = await searchObjects(query);
      if (res.success) {
        setResults(res.results);
        if (res.results.length === 0) {
          toast.info('검색 결과가 없습니다.');
        }
      } else {
        setError('검색에 실패했습니다.');
        setResults([]);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : '검색 중 오류가 발생했습니다.';
      setError(msg);
      setResults([]);
      toast.error(msg);
    } finally {
      setIsSearching(false);
    }
  }, []);

  /** 선택한 항목의 자식으로 드릴다운 */
  const drillDown = useCallback(
    async (item: ObjectSearchResult) => {
      setIsDrilling(true);
      setError(null);

      try {
        const res = await getChildren(
          item.object_type,
          item.id_value,
          item.properties,
        );

        if (res.success) {
          // 현재 상태를 이력에 저장 (goBack 복원용)
          setHistory((prev) => [
            ...prev,
            { results, children },
          ]);

          // 브레드크럼에 현재 항목 추가
          setBreadcrumb((prev) => [
            ...prev,
            {
              object_type: item.object_type,
              name_value: item.name_value,
              id_value: item.id_value,
              properties: item.properties,
            },
          ]);

          // 자식 결과 표시 (자식의 items를 평면화하여 results로도 설정)
          setChildren(res.children);
          const flatItems = res.children.flatMap((g) => g.items);
          setResults(flatItems);
          setSelectedItem(null);
        } else {
          setError('자식 항목 조회에 실패했습니다.');
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : '드릴다운 중 오류가 발생했습니다.';
        setError(msg);
        toast.error(msg);
      } finally {
        setIsDrilling(false);
      }
    },
    [results, children],
  );

  /** 브레드크럼 특정 위치로 복귀 */
  const goBack = useCallback(
    (index: number) => {
      // index === -1 이면 루트(검색 결과)로 복귀
      if (index < 0) {
        // 최초 검색 결과로 복원
        if (history.length > 0) {
          const first = history[0];
          setResults(first.results);
          setChildren(first.children);
        }
        setBreadcrumb([]);
        setHistory([]);
        setSelectedItem(null);
        return;
      }

      // index 위치까지의 상태로 복원
      const targetHistoryIndex = index; // history[index]가 해당 단계의 상태
      if (targetHistoryIndex < history.length) {
        const snapshot = history[targetHistoryIndex];
        setResults(snapshot.results);
        setChildren(snapshot.children);
      }

      // 브레드크럼 자르기 (index 위치까지 유지하되 해당 위치의 항목이 현재 드릴다운 대상이므로 다시 드릴)
      setBreadcrumb((prev) => prev.slice(0, index));
      setHistory((prev) => prev.slice(0, index));
      setSelectedItem(null);
    },
    [history],
  );

  /** 속성 패널에 표시할 항목 선택 */
  const selectItem = useCallback((item: ObjectSearchResult | null) => {
    setSelectedItem(item);
  }, []);

  /** 전체 상태 초기화 */
  const reset = useCallback(() => {
    setResults([]);
    setChildren([]);
    setBreadcrumb([]);
    setSelectedItem(null);
    setIsSearching(false);
    setIsDrilling(false);
    setError(null);
    setSearchQuery('');
    setHistory([]);
  }, []);

  return {
    search,
    drillDown,
    goBack,
    selectItem,
    results,
    children,
    breadcrumb,
    selectedItem,
    isSearching,
    isDrilling,
    error,
    searchQuery,
    reset,
  };
}
