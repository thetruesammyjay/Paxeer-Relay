import type { Metadata } from "next";
import { AgentDirectory } from "@/components/agent-directory";
export const metadata: Metadata = { title: "Agents" };
export default function Page() {
  return <AgentDirectory />;
}
