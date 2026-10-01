import type { Metadata } from "next";
import { SettlementReview } from "@/components/settlement-review";

export const metadata: Metadata = { title: "Settlement review" };

export default function SettlementReviewPage() {
  return <SettlementReview />;
}
