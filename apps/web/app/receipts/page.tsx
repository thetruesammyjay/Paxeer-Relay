import type { Metadata } from "next";

export const metadata: Metadata = { title: "Receipts" };

export default function ReceiptsPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold">Receipts</h1>
      {/* Signed execution receipt browser — implemented in a later step */}
    </div>
  );
}
