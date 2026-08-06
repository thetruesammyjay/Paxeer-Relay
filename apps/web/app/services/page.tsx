import type { Metadata } from "next";

export const metadata: Metadata = { title: "Services" };

export default function ServicesPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold">Services</h1>
      {/* Service listing + publish button — implemented in a later step */}
    </div>
  );
}
