"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface ReceiptRecord {
  id: string;
  tool_call_id: string;
  agent_id: string;
  provider_id: string;
  service_id: string;
  service_version: string;
  capability: string;
  request_hash: string;
  response_hash: string;
  payment_amount: string;
  payment_currency: string;
  payment_scheme: string;
  payment_network: string | null;
  payment_asset: string | null;
  payment_transaction: string | null;
  layerx_transaction: string | null;
  execution_latency_ms: number;
  execution_status: string;
  receipt_hash: string | null;
  signature: string | null;
  signing_key_id: string | null;
  issued_at: string;
}

/** Read the latest tenant-scoped receipt summaries for one in-memory key. */
export function useReceipts(apiKey: string, connectionId: string) {
  return useQuery({
    queryKey: ["receipts", connectionId],
    queryFn: ({ signal }) =>
      apiFetch<ReceiptRecord[]>("/v1/receipts?limit=100", {
        token: apiKey,
        signal,
        cache: "no-store",
        integerFieldsAsStrings: ["payment_amount"],
      }),
    enabled: Boolean(apiKey && connectionId),
    staleTime: 10_000,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}
