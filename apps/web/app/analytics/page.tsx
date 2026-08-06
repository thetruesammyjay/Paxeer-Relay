import type { Metadata } from "next";

export const metadata: Metadata = { title: "Analytics" };

export default function AnalyticsPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold">Analytics</h1>
      {/* Spend charts, capability breakdown, provider leaderboard — implemented in a later step */}
    </div>
  );
}
