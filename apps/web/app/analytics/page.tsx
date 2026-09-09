import type { Metadata } from "next";
import { ResourcePage } from "@/components/resource-page";
export const metadata: Metadata = { title: "Analytics" };
export default function Page() {
  return <ResourcePage kind="analytics" />;
}
