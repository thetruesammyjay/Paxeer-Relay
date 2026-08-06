import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: string;
}

const TONES: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  paused: "bg-yellow-100 text-yellow-800",
  suspended: "bg-red-100 text-red-800",
  pending: "bg-slate-100 text-slate-700",
};

/** Small coloured pill used across tables to show a resource's status. */
export function StatusBadge({ status }: StatusBadgeProps) {
  const tone = TONES[status.toLowerCase()] ?? TONES.pending;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        tone,
      )}
    >
      {status}
    </span>
  );
}
