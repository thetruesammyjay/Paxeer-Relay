import type { Metadata } from "next";
import { LiveDashboard } from "@/components/live-dashboard";

export const metadata: Metadata = { title: "Production operations" };

export default function AdminDashboardPage() {
  return <LiveDashboard mode="admin" />;
}
