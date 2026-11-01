import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteAnalysis, getAnalysis, listAnalyses, type ListParams } from "../api/client";
import { ApiError } from "../api/client";
import { isActiveStatus } from "../lib/meta";

export const POLL_INTERVAL_MS = 1500;

export const queryKeys = {
  analyses: ["analyses"] as const,
  list: (params: ListParams) => ["analyses", "list", params] as const,
  detail: (id: string) => ["analyses", "detail", id] as const,
};

export function useAnalysesList(params: ListParams) {
  return useQuery({
    queryKey: queryKeys.list(params),
    queryFn: () => listAnalyses(params),
    placeholderData: keepPreviousData,
  });
}

export function useAnalysis(id: string) {
  return useQuery({
    queryKey: queryKeys.detail(id),
    queryFn: () => getAnalysis(id),
    refetchInterval: (query) => (isActiveStatus(query.state.data?.status) ? POLL_INTERVAL_MS : false),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  });
}

export function useDeleteAnalysis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteAnalysis(id),
    onSuccess: (_data, id) => {
      qc.removeQueries({ queryKey: queryKeys.detail(id) });
      return qc.invalidateQueries({ queryKey: queryKeys.analyses });
    },
  });
}
