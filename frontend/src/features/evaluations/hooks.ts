import { useMutation, useQuery } from "@tanstack/react-query";

import { createEvaluation, getEvaluationDetail, retryEvaluation } from "./api";

const DETAIL_POLL_INTERVAL_MS = 30_000;

export function useCreateEvaluation() {
  return useMutation({
    mutationFn: createEvaluation,
  });
}

export function useEvaluationDetail(evaluationId: string | undefined) {
  return useQuery({
    queryKey: ["evaluation-detail", evaluationId],
    queryFn: () => getEvaluationDetail(evaluationId!),
    enabled: Boolean(evaluationId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "running" ? DETAIL_POLL_INTERVAL_MS : false;
    },
  });
}

export function useRetryEvaluation() {
  return useMutation({
    mutationFn: retryEvaluation,
  });
}
