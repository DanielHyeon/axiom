import { useQuery } from '@tanstack/react-query';
import { getHistory } from '../api/oracleNl2sqlApi';

export function useQueryHistory(datasourceId?: string, page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ['nl2sql', 'history', datasourceId, page, pageSize],
    queryFn: () => getHistory({ datasource_id: datasourceId, page, page_size: pageSize }),
    staleTime: 60 * 1000,
  });
}
