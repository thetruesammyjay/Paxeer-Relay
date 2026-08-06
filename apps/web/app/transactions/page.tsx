import type { Metadata } from "next";

export const metadata: Metadata = { title: "Transactions" };

export default function TransactionsPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold">Transactions</h1>
      {/* Paginated tool-call transaction log — implemented in a later step */}
    </div>
  );
}
