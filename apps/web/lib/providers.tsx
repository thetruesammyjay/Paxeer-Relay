"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { ApiSessionProvider } from "@/lib/api-session";

/**
 * Client-side TanStack Query provider. Wrap dashboard layouts with this so
 * data hooks share a single query cache.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={client}>
      <ApiSessionProvider>{children}</ApiSessionProvider>
    </QueryClientProvider>
  );
}
