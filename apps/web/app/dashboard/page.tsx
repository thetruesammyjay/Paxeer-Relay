import type { Metadata } from "next";
import { LiveDashboard } from "@/components/live-dashboard";

export const metadata: Metadata = { title: "Production workspace" };

export default function DashboardPage() {
  return <LiveDashboard mode="workspace" />;
}
