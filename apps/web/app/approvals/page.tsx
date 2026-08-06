import type { Metadata } from "next";

export const metadata: Metadata = { title: "Approvals" };

export default function ApprovalsPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold">Approvals</h1>
      {/* Pending approval requests — implemented in a later step */}
    </div>
  );
}
