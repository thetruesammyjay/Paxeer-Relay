"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface Agent {
  id: string;
  name: string;
  slug: string;
  status: string;
  wallet_address: string | null;
  created_at: string;
}

/** Fetch the list of agents for the current tenant. */
export function useAgents(token?: string) {
  return useQuery({
    queryKey: ["agents"],
    queryFn: () => apiFetch<Agent[]>("/v1/agents", { token }),
  });
}
