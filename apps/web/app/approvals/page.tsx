import type { Metadata } from "next";
import { ResourcePage } from "@/components/resource-page";
export const metadata: Metadata = { title: "Approvals" };
export default function Page() {
  return <ResourcePage kind="approvals" />;
}
