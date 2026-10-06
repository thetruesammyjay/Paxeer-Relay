"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface ServicePrice {
  amount_atomic: string;
  currency: string;
  decimals: number;
}

export interface ServiceHealthConfig {
  endpoint: string;
  interval_seconds: number;
  timeout_seconds: number;
  failure_threshold: number;
}

export interface ServiceHealthSettings extends ServiceHealthConfig {
  last_check_at?: string | null;
  last_check_passing?: boolean | null;
  consecutive_health_failures?: number;
  last_check_status_code?: number | null;
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

export type ServiceProtocolName = "http" | "mcp";

export interface ServiceCreateInput {
  name: string;
  slug: string;
  capability: string;
  protocols: ServiceProtocolName[];
  mcp_tool_name?: string | null;
  mcp_input_schema?: Record<string, unknown> | null;
  price_per_call: ServicePrice;
  base_url: string;
  endpoint_url: string;
  health: ServiceHealthConfig;
  version: string;
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

export function publishService(
  token: string,
  providerId: string,
  input: ServiceCreateInput,
) {
  // Keep the USDX amount exact when converting the browser form to JSON.
  const body = JSON.stringify(input).replace(
    /"amount_atomic":"(\d+)"/,
    '"amount_atomic":$1',
  );
  return apiFetch<ServiceRecord>(
    `/v1/services/providers/${encodeURIComponent(providerId)}`,
    {
      method: "POST",
      token,
      body,
      cache: "no-store",
      integerFieldsAsStrings: ["amount_atomic"],
    },
  );
}

export function updateServiceStatus(
  token: string,
  serviceId: string,
  status: "active" | "inactive",
) {
  return apiFetch<ServiceRecord>(
    `/v1/services/${encodeURIComponent(serviceId)}/status`,
    {
      method: "PATCH",
      token,
      body: JSON.stringify({ status }),
      cache: "no-store",
      integerFieldsAsStrings: ["amount_atomic"],
    },
  );
}
