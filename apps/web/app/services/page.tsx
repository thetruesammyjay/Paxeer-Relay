import type { Metadata } from "next";
import { ServiceDirectory } from "@/components/service-directory";
export const metadata: Metadata = { title: "Services" };
export default function Page() {
  return <ServiceDirectory />;
}
