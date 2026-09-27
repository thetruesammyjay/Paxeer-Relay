import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { Providers } from "@/lib/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: { template: "%s | PaxRelay", default: "PaxRelay" },
  description: "Route, pay, enforce, and verify every agent-to-service call.",
  icons: {
    icon: "/PaxRelay-ico.png",
    shortcut: "/PaxRelay-ico.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
