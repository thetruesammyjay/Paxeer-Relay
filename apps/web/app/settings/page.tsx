import type { Metadata } from "next";
import { ResourcePage } from "@/components/resource-page";
export const metadata: Metadata = { title: "Settings" };
export default function Page() {
  return <ResourcePage kind="settings" />;
}
