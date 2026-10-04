"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface ServicePrice {
  amount_atomic: string;
  currency: string;
  decimals: number;
}

export interface ServiceHealthSettings {
  endpoint: string;
  interval_seconds: number;
  timeout_seconds: number;
  failure_threshold: number;
}

export interface ServiceRecord {
  id: string;
  provider_id: string;
  name: string;
  slug: string;
  capability: string;
  protocols: string[];
  status: string;
  base_url: string | null;
  price_per_call: ServicePrice | null;
  health: ServiceHealthSettings;
  description: string | null;
}

/** Fetch the latest tenant services for one in-memory API-key session. */
export function useServices(token: string, connectionId: string) {
  return useQuery({
    queryKey: ["services", connectionId],
    queryFn: ({ signal }) =>
      apiFetch<ServiceRecord[]>("/v1/services", {
        token,
        signal,
        cache: "no-store",
        integerFieldsAsStrings: ["amount_atomic"],
      }),
    enabled: Boolean(token && connectionId),
    staleTime: 10_000,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}
