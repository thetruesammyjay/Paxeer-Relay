import type { Metadata } from "next";

export const metadata: Metadata = { title: "Dashboard" };

export default function DashboardPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      {/* KPI cards, spend chart, recent activity — implemented in a later step */}
    </div>
  );
}
