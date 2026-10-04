"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface PolicySummary {
  id: string;
  name: string;
  description: string | null;
  mode: "observe" | "warn" | "enforce";
  version: number;
  is_active: boolean;
}

export interface PolicyMoney {
  amount_atomic: string | number;
  currency: string;
  decimals: number;
}

export interface PolicyRules {
  maximum_per_call: PolicyMoney | null;
  daily_budget: PolicyMoney | null;
  monthly_budget: PolicyMoney | null;
  allowed_capabilities: string[];
  allowed_providers: string[];
  blocked_providers: string[];
  allowed_contracts: string[];
  minimum_provider_reputation: number | null;
  minimum_provider_success_rate: number | null;
  maximum_accepted_latency_ms: number | null;
  approval_threshold: PolicyMoney | null;
  maximum_consecutive_failures: number | null;
  maximum_drawdown: PolicyMoney | null;
  session_expiry_seconds: number | null;
  allowed_currencies: string[];
}

export interface PolicyAssignment {
  id: string;
  agent_id: string;
  policy_id: string;
  assigned_at: string;
}

export interface PolicyDetail extends PolicySummary {
  rules: PolicyRules;
  assignments: PolicyAssignment[];
}

export interface PolicyCreateInput {
  name: string;
  description: string | null;
  mode: "observe" | "warn" | "enforce";
  maximum_per_call: PolicyMoney | null;
  daily_budget: PolicyMoney | null;
  monthly_budget: PolicyMoney | null;
  allowed_capabilities: string[];
  allowed_providers: string[];
  blocked_providers: string[];
  approval_threshold: PolicyMoney | null;
}

export interface PolicyFilters {
  search: string;
  mode: string;
  active: string;
}

/** Fetch tenant policies for one in-memory API-key session. */
export function usePolicies(
  token: string,
  connectionId: string,
  filters: PolicyFilters,
) {
  return useQuery({
    queryKey: [
      "policies",
      connectionId,
      filters.search,
      filters.mode,
      filters.active,
    ],
    queryFn: ({ signal }) => {
      const params = new URLSearchParams({ limit: "100" });
      if (filters.search) params.set("search", filters.search);
      if (filters.mode) params.set("mode", filters.mode);
      if (filters.active) params.set("is_active", filters.active);

      return apiFetch<PolicySummary[]>(`/v1/policies?${params.toString()}`, {
        token,
        signal,
        cache: "no-store",
      });
    },
    enabled: Boolean(token && connectionId),
    staleTime: 10_000,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}

export function usePolicy(
  token: string,
  connectionId: string,
  policyId: string,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["policy-detail", connectionId, policyId],
    queryFn: ({ signal }) =>
      apiFetch<PolicyDetail>(`/v1/policies/${encodeURIComponent(policyId)}`, {
        token,
        signal,
        cache: "no-store",
        integerFieldsAsStrings: ["amount_atomic"],
      }),
    enabled: Boolean(token && connectionId && policyId && enabled),
    staleTime: 10_000,
  });
}

export function createPolicy(token: string, input: PolicyCreateInput) {
  // Keep atomic amounts as exact JSON integers without passing through Number.
  const body = JSON.stringify(input).replace(
    /"amount_atomic":"(\d+)"/g,
    '"amount_atomic":$1',
  );
  return apiFetch<PolicySummary>("/v1/policies", {
    method: "POST",
    token,
    body,
    cache: "no-store",
  });
}

export function assignPolicy(
  token: string,
  policyId: string,
  agentId: string,
) {
  return apiFetch<PolicyAssignment>(
    `/v1/policies/${encodeURIComponent(policyId)}/assign`,
    {
      method: "POST",
      token,
      body: JSON.stringify({ agent_id: agentId }),
      cache: "no-store",
    },
  );
}
