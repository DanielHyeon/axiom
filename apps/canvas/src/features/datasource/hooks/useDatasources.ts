import { useState, useEffect, useCallback } from 'react';
import {
  listDatasources,
  createDatasource,
  deleteDatasource,
  testConnection,
  getDatasourceTypes,
  type DatasourceItem,
  type DatasourceCreatePayload,
  type EngineType,
} from '../api/weaverDatasourceApi';

export function useDatasources() {
  const [datasources, setDatasources] = useState<DatasourceItem[]>([]);
  const [engineTypes, setEngineTypes] = useState<EngineType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refetch = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const [listRes, typesRes] = await Promise.all([listDatasources(), getDatasourceTypes()]);
      setDatasources(listRes.datasources);
      setEngineTypes(typesRes.types);
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
      setDatasources([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  const addDatasource = useCallback(async (payload: DatasourceCreatePayload) => {
    await createDatasource(payload);
    await refetch();
  }, [refetch]);

  const removeDatasource = useCallback(async (name: string) => {
    await deleteDatasource(name);
    await refetch();
  }, [refetch]);

  const test = useCallback(async (name: string) => {
    return testConnection(name);
  }, []);

  return {
    datasources,
    engineTypes,
    loading,
    error,
    refetch,
    addDatasource,
    removeDatasource,
    test,
  };
}
