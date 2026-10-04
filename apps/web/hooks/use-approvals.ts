"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export interface Approval {
  id: string;
  tool_call_id: string;
  agent_id: string;
  capability: string;
  provider_id: string | null;
  service_version_id: string | null;
  amount_atomic: string;
  currency: string;
  decimals: number;
  recipient_address: string | null;
  request_hash: string | null;
  policy_id: string | null;
  policy_version: number | null;
  status: string;
  reason: string | null;
  decision_reason: string | null;
  expires_at: string | null;
  decided_at: string | null;
  created_at: string;
}

export type ApprovalDecision = "approved" | "rejected";

/** Read the latest approvals visible to this API-key session. */
export function useApprovals(
  token: string,
  connectionId: string,
  status: string,
) {
  return useQuery({
    queryKey: ["approvals", connectionId, status],
    queryFn: ({ signal }) => {
      const params = new URLSearchParams({ limit: "100" });
      if (status) params.set("status", status);
      return apiFetch<Approval[]>(`/v1/approvals?${params.toString()}`, {
        token,
        signal,
        cache: "no-store",
        integerFieldsAsStrings: ["amount_atomic"],
      });
    },
    enabled: Boolean(token && connectionId),
    staleTime: 10_000,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}

interface DecideApprovalInput {
  approvalId: string;
  decision: ApprovalDecision;
  reason?: string;
}

/** Submit one explicit human decision and refresh this session's queue. */
export function useDecideApproval(token: string, connectionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ approvalId, decision, reason }: DecideApprovalInput) =>
      apiFetch<Approval>(`/v1/approvals/${approvalId}/decision`, {
        method: "POST",
        token,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, reason }),
        integerFieldsAsStrings: ["amount_atomic"],
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["approvals", connectionId],
      }),
  });
}
