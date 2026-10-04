"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface Transaction {
  id: string;
  agent_id: string;
  capability: string;
  request_state: string;
  payment_state: string;
  execution_state: string;
  created_at: string;
  updated_at: string;
}

export interface ExecutionAttempt {
  id: string;
  tool_call_id: string;
  provider_id: string;
  service_version_id: string;
  attempt_number: number;
  execution_state: string;
  request_forwarded_at: string | null;
  response_received_at: string | null;
  latency_ms: number | null;
  http_status_code: number | null;
  provider_error_code: string | null;
  created_at: string;
  updated_at: string;
}

interface TransactionFilters {
  apiKey: string;
  connectionId: string;
  requestState: string;
  paymentState: string;
}

/** Read the latest tenant-scoped tool calls with the optional API filters. */
export function useTransactions({
  apiKey,
  connectionId,
  requestState,
  paymentState,
}: TransactionFilters) {
  return useQuery({
    queryKey: ["transactions", connectionId, requestState, paymentState],
    queryFn: ({ signal }) => {
      const params = new URLSearchParams({ limit: "100" });
      if (requestState) params.set("request_state", requestState);
      if (paymentState) params.set("payment_state", paymentState);

      return apiFetch<Transaction[]>(`/v1/transactions?${params.toString()}`, {
        token: apiKey,
        signal,
        cache: "no-store",
      });
    },
    enabled: Boolean(apiKey && connectionId),
    staleTime: 10_000,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}

/** Load bounded operational metadata for one tenant-owned transaction. */
export function useExecutionAttempts({
  apiKey,
  connectionId,
  toolCallId,
}: {
  apiKey: string;
  connectionId: string;
  toolCallId: string | null;
}) {
  return useQuery({
    queryKey: ["execution-attempts", connectionId, toolCallId],
    queryFn: ({ signal }) =>
      apiFetch<ExecutionAttempt[]>(
        `/v1/transactions/${encodeURIComponent(toolCallId!)}/execution-attempts?limit=100`,
        { token: apiKey, signal, cache: "no-store" },
      ),
    enabled: Boolean(apiKey && connectionId && toolCallId),
    staleTime: 10_000,
  });
}
