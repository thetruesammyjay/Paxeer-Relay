"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export type ReconciliationStatus =
  | "mismatch"
  | "awaiting_external"
  | "layerx_confirmed"
  | "reconciled";

export interface ReconciliationIssue {
  code: string;
  expected?: unknown;
  actual?: unknown;
}

export interface SettlementReconciliation {
  id: string;
  payment_id: string;
  payment_state: string;
  reconciliation_status: ReconciliationStatus | "anchored";
  layerx_transaction_hash: string | null;
  layerx_batch_id: string | null;
  l1_settlement_id: string | null;
  l1_block_number: number | null;
  l1_transaction_hash: string | null;
  l1_commitment_hash: string | null;
  internal_checked_at: string | null;
  last_checked_at: string | null;
  attempt_count: number;
  next_attempt_at: string | null;
  last_error: string | null;
  reconciled_at: string | null;
  mismatch_details: { issues?: ReconciliationIssue[] } | null;
  created_at: string;
  updated_at: string;
}

export interface SettlementReconciliationPage {
  items: SettlementReconciliation[];
  next_cursor_created_at: string | null;
  next_cursor_id: string | null;
}

export interface ReconciliationCursor {
  createdAt: string;
  id: string;
}

interface QueryOptions {
  token?: string;
  connectionVersion: number;
  status: ReconciliationStatus;
  cursor: ReconciliationCursor | null;
}

/** Load one tenant-scoped page of the read-only reconciliation queue. */
export function useSettlementReconciliation({
  token,
  connectionVersion,
  status,
  cursor,
}: QueryOptions) {
  return useQuery({
    queryKey: [
      "settlement-reconciliation",
      connectionVersion,
      status,
      cursor?.createdAt ?? null,
      cursor?.id ?? null,
    ],
    queryFn: ({ signal }) => {
      const query = new URLSearchParams({ status, limit: "50" });
      if (cursor) {
        query.set("before_created_at", cursor.createdAt);
        query.set("before_id", cursor.id);
      }
      return apiFetch<SettlementReconciliationPage>(
        `/v1/settlements/reconciliation?${query.toString()}`,
        { token, signal },
      );
    },
    enabled: Boolean(token),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}
