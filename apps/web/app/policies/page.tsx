import type { Metadata } from "next";

export const metadata: Metadata = { title: "Policies" };

export default function PoliciesPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold">Policies</h1>
      {/* Policy list + policy builder — implemented in a later step */}
    </div>
  );
}
