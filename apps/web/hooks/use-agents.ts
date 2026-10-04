"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface Agent {
  id: string;
  name: string;
  slug: string;
  environment: string;
  status: string;
  wallet_address: string | null;
  description: string | null;
  created_at: string;
}

/** Fetch the latest agents for the tenant represented by this key session. */
export function useAgents(token: string, connectionId: string) {
  return useQuery({
    queryKey: ["agents", connectionId],
    queryFn: ({ signal }) =>
      apiFetch<Agent[]>("/v1/agents?limit=100", {
        token,
        signal,
        cache: "no-store",
      }),
    enabled: Boolean(token && connectionId),
    staleTime: 10_000,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}
