import type { Metadata } from "next";
import { PolicyDirectory } from "@/components/policy-directory";
export const metadata: Metadata = { title: "Policies" };
export default function Page() {
  return <PolicyDirectory />;
}
