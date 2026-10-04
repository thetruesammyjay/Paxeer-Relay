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
