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
