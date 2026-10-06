import type { Metadata } from "next";
import { LiveDashboard } from "@/components/live-dashboard";

export const metadata: Metadata = { title: "Provider activity" };

export default function CreatorDashboardPage() {
  return <LiveDashboard mode="creator" />;
}
