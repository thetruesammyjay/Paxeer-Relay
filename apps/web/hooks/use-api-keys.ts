"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface ApiKeyRecord {
  id: string;
  name: string;
  key_prefix: string;
  key_type: "test" | "live";
  scopes: string;
  expires_at: string | null;
  created_at: string | null;
  last_used_at: string | null;
  is_active: boolean;
  raw_key?: string | null;
}

export interface CreateApiKeyInput {
  name: string;
  key_type: "test" | "live";
  scopes: string;
  expires_in_days: number;
}

/** Read the latest tenant-scoped API-key inventory for one key session. */
export function useApiKeys(apiKey: string, connectionId: string) {
  return useQuery({
    queryKey: ["api-keys", connectionId],
    queryFn: ({ signal }) =>
      apiFetch<ApiKeyRecord[]>("/v1/api-keys?limit=100", {
        token: apiKey,
        signal,
        cache: "no-store",
      }),
    enabled: Boolean(apiKey && connectionId),
    staleTime: 10_000,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}

export function createApiKey(apiKey: string, input: CreateApiKeyInput) {
  return apiFetch<ApiKeyRecord>("/v1/api-keys", {
    method: "POST",
    token: apiKey,
    body: JSON.stringify(input),
    cache: "no-store",
  });
}

export function revokeApiKey(apiKey: string, keyId: string) {
  return apiFetch<void>(`/v1/api-keys/${encodeURIComponent(keyId)}`, {
    method: "DELETE",
    token: apiKey,
    cache: "no-store",
  });
}
