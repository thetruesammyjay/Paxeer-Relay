import type { Metadata } from "next";
import { ProviderDirectory } from "@/components/provider-directory";
export const metadata: Metadata = { title: "Providers" };
export default function Page() {
  return <ProviderDirectory />;
}
