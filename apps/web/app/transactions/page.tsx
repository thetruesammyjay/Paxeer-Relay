import type { Metadata } from "next";
import { TransactionActivity } from "@/components/transaction-activity";
export const metadata: Metadata = { title: "Transactions" };
export default function Page() {
  return <TransactionActivity />;
}
