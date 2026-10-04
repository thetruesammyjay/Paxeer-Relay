import type { Metadata } from "next";
import { ReceiptDirectory } from "@/components/receipt-directory";
export const metadata: Metadata = { title: "Receipts" };
export default function Page() {
  return <ReceiptDirectory />;
}
