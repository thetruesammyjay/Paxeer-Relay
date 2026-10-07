"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface ProviderRecord {
  id: string;
  name: string;
  slug: string;
  environment: string;
  wallet_address: string | null;
  layerx_account_id: string | null;
  solana_devnet_address: string | null;
  status: string;
  is_verified: boolean;
  description: string | null;
  website_url: string | null;
}

export interface ProviderCreateInput {
  name: string;
  slug: string;
  wallet_address: string | null;
  layerx_account_id: string | null;
  solana_devnet_address: string | null;
  description: string | null;
  website_url: string | null;
}

export interface ProviderFilters {
  search: string;
  status: string;
}

/** Fetch the latest tenant providers for one in-memory API-key session. */
export function useProviders(
  token: string,
  connectionId: string,
  filters: ProviderFilters,
) {
  return useQuery({
    queryKey: ["providers", connectionId, filters.search, filters.status],
    queryFn: ({ signal }) => {
      const params = new URLSearchParams({ limit: "100" });
      if (filters.search) params.set("search", filters.search);
      if (filters.status) params.set("status", filters.status);

      return apiFetch<ProviderRecord[]>(`/v1/providers?${params.toString()}`, {
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

export function createProvider(token: string, input: ProviderCreateInput) {
  return apiFetch<ProviderRecord>("/v1/providers", {
    method: "POST",
    token,
    body: JSON.stringify(input),
    cache: "no-store",
  });
}
