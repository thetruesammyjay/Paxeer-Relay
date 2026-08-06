import { DocsLayout } from "fumadocs-ui/layouts/docs";
import type { ReactNode } from "react";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <DocsLayout
      tree={{
        name: "PaxRelay",
        children: [
          {
            type: "page",
            name: "Introduction",
            url: "/docs",
          },
          {
            type: "folder",
            name: "Getting Started",
            children: [
              { type: "page", name: "Installation", url: "/docs/installation" },
              { type: "page", name: "Quickstart", url: "/docs/quickstart" },
            ],
          },
        ],
      }}
    >
      {children}
    </DocsLayout>
  );
}
