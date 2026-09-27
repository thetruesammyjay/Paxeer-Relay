interface StatusBadgeProps {
  status: string;
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
};

/** Status label with a written state and a matching, non-color-only marker. */
export function StatusBadge({ status }: StatusBadgeProps) {
  const tone = TONES[status.toLowerCase()] ?? "neutral";
  return <span className={"status " + tone}>{status}</span>;
}
