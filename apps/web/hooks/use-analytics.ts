"use client";

import { useEffect, useState } from "react";
import { ApiError, apiFetch } from "@/lib/api-client";

export interface AnalyticsSpend {
  period: string;
  start_date: string;
  end_date: string;
  total_amount_atomic: number;
  currency: string;
  decimals: number;
  transaction_count: number;
}

export interface AnalyticsCapability {
  capability: string;
  total_amount_atomic: number;
  currency: string;
  decimals: number;
  call_count: number;
}

export interface AnalyticsData {
  spend: AnalyticsSpend;
  capabilities: AnalyticsCapability[];
}

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "The API key was not accepted. Check it and try again.";
    }
    if (error.status === 403) {
      return "This key needs analytics:read access for this project and environment.";
    }
    if (error.status === 404) {
      return "The analytics endpoint was not found. Update the API and try again.";
    }
    if (error.status === 429) {
      return "Too many requests. Wait a moment, then try again.";
    }
    return `Analytics could not be loaded (HTTP ${error.status}). Try again shortly.`;
  }
  return "The API could not be reached. Check that it is running and try again.";
}

export function useAnalytics(apiKey: string, refreshVersion: number) {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!apiKey) {
      setData(null);
      setError("");
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    const end = new Date();
    const start = new Date(end.getTime() - 30 * 24 * 60 * 60 * 1000);
    const range = new URLSearchParams({
      start_date: start.toISOString(),
      end_date: end.toISOString(),
    });

    async function loadAnalytics() {
      setLoading(true);
      setError("");
      try {
        const [spend, capabilities] = await Promise.all([
          apiFetch<AnalyticsSpend>(`/v1/analytics/spend?${range.toString()}`, {
            token: apiKey,
            signal: controller.signal,
            cache: "no-store",
          }),
          apiFetch<AnalyticsCapability[]>(
            `/v1/analytics/capabilities?${range.toString()}&limit=100`,
            {
              token: apiKey,
              signal: controller.signal,
              cache: "no-store",
            },
          ),
        ]);
        setData({ spend, capabilities });
      } catch (requestError) {
        if (controller.signal.aborted) return;
        setData(null);
        setError(getErrorMessage(requestError));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    void loadAnalytics();
    return () => controller.abort();
  }, [apiKey, refreshVersion]);

  return { data, error, loading };
}
