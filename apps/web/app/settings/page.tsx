import type { Metadata } from "next";
import { ApiKeyInventory } from "@/components/api-key-inventory";
export const metadata: Metadata = { title: "Settings" };
export default function Page() {
  return <ApiKeyInventory />;
}
