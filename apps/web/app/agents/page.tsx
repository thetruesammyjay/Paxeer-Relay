import type { Metadata } from "next";

export const metadata: Metadata = { title: "Agents" };

export default function AgentsPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold">Agents</h1>
      {/* Agent list table + create button — implemented in a later step */}
    </div>
  );
}
