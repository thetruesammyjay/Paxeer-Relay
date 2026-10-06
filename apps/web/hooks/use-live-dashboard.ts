"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { Approval } from "@/hooks/use-approvals";
import type { ProviderRecord } from "@/hooks/use-providers";
import type { ReceiptRecord } from "@/hooks/use-receipts";
import type { ServiceRecord } from "@/hooks/use-services";
import type { Transaction } from "@/hooks/use-transactions";

export interface DashboardResource<T> {
  data: T | null;
  problem: { status: number | null; message: string } | null;
}

export interface LiveDashboardData {
  services: DashboardResource<ServiceRecord[]>;
  transactions: DashboardResource<Transaction[]>;
  spend: DashboardResource<DashboardSpend>;
  providers?: DashboardResource<ProviderRecord[]>;
  approvals?: DashboardResource<Approval[]>;
  receipts?: DashboardResource<ReceiptRecord[]>;
}

export type LiveDashboardMode = "workspace" | "admin" | "creator";

export const DASHBOARD_SCOPES = {
  providers: "providers:read",
  services: "services:read",
  transactions: "transactions:read",
  approvals: "approvals:read",
  receipts: "receipts:read",
  spend: "analytics:read",
} as const;

export interface DashboardSpend {
  period: string;
  start_date: string;
  end_date: string;
  total_amount_atomic: string;
  currency: string;
  decimals: number;
  transaction_count: number;
}

function rangeForLast30Days(): URLSearchParams {
  const end = new Date();
  const start = new Date(end.getTime() - 30 * 24 * 60 * 60 * 1000);
  return new URLSearchParams({
    start_date: start.toISOString(),
    end_date: end.toISOString(),
  });
}

async function loadResource<T>(
  request: Promise<T>,
  signal: AbortSignal,
): Promise<DashboardResource<T>> {
  try {
    return { data: await request, problem: null };
  } catch (error) {
    if (signal.aborted) throw error;
    if (error instanceof ApiError) {
      return {
        data: null,
        problem: { status: error.status, message: error.message },
      };
    }
    return {
      data: null,
      problem: {
        status: null,
        message: error instanceof Error ? error.message : "The API request failed.",
      },
    };
  }
}

/** Load independent production resources so each key scope remains usable. */
export function useLiveDashboard(
  apiKey: string,
  connectionVersion: number,
  mode: LiveDashboardMode,
) {
  return useQuery({
    queryKey: ["live-dashboard", connectionVersion, mode],
    queryFn: async ({ signal }): Promise<LiveDashboardData> => {
      const range = rangeForLast30Days().toString();
      const options = { token: apiKey, signal, cache: "no-store" as const };
      const providersRequest = mode === "admin"
        ? loadResource(apiFetch<ProviderRecord[]>("/v1/providers?limit=100", options), signal)
        : undefined;
      const approvalsRequest = mode !== "creator"
        ? loadResource(
            apiFetch<Approval[]>("/v1/approvals?status=pending&limit=100", {
              ...options,
              integerFieldsAsStrings: ["amount_atomic"],
            }),
            signal,
          )
        : undefined;
      const receiptsRequest = mode === "creator"
        ? loadResource(
            apiFetch<ReceiptRecord[]>("/v1/receipts?limit=100", {
              ...options,
              integerFieldsAsStrings: ["payment_amount"],
            }),
            signal,
          )
        : undefined;
      const [services, transactions, spend, providers, approvals, receipts] = await Promise.all([
        loadResource(apiFetch<ServiceRecord[]>("/v1/services", options), signal),
        loadResource(apiFetch<Transaction[]>("/v1/transactions?limit=100", options), signal),
        loadResource(
          apiFetch<DashboardSpend>(`/v1/analytics/spend?${range}`, {
            ...options,
            integerFieldsAsStrings: ["total_amount_atomic"],
          }),
          signal,
        ),
        providersRequest,
        approvalsRequest,
        receiptsRequest,
      ]);
      const data: LiveDashboardData = { services, transactions, spend };
      if (providers) data.providers = providers;
      if (approvals) data.approvals = approvals;
      if (receipts) data.receipts = receipts;
      return data;
    },
    enabled: Boolean(apiKey),
    staleTime: 10_000,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}
