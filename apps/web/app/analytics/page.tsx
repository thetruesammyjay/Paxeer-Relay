import type { Metadata } from "next";
import { AnalyticsDashboard } from "@/components/analytics-dashboard";
export const metadata: Metadata = { title: "Analytics" };
export default function Page() {
  return <AnalyticsDashboard />;
}
