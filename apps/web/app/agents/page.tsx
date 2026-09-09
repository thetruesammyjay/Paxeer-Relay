import type { Metadata } from "next";
import { ResourcePage } from "@/components/resource-page";
export const metadata: Metadata = { title: "Agents" };
export default function Page() {
  return <ResourcePage kind="agents" />;
}
