interface StatusBadgeProps {
  status: string;
  label?: string;
}

const TONES: Record<string, string> = {
  active: "active",
  settled: "settled",
  verified: "verified",
  pending: "pending",
  review: "review",
  routing: "routing",
  paused: "paused",
  denied: "denied",
  suspended: "suspended",
  failed: "failed",
  awaiting_external: "pending",
  layerx_confirmed: "routing",
  mismatch: "failed",
  reconciled: "settled",
  anchored: "settled",
};

/** Status label with a written state and a matching, non-color-only marker. */
export function StatusBadge({ status, label }: StatusBadgeProps) {
  const tone = TONES[status.toLowerCase()] ?? "neutral";
  return <span className={"status " + tone}>{label ?? status}</span>;
}
