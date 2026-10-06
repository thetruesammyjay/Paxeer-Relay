"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api-client";

export interface WorkspaceContext {
  organisation_id: string;
  project_id: string;
  environment: "development" | "test" | "staging" | "production";
  api_key_id: string;
  scopes: string[];
}

type ApiSessionStatus = "disconnected" | "checking" | "connected" | "error";

interface ApiSessionValue {
  apiKey: string;
  workspace: WorkspaceContext | null;
  connectionVersion: number;
  status: ApiSessionStatus;
  error: string;
  connect: (key: string) => Promise<boolean>;
  disconnect: () => void;
}

const ApiSessionContext = createContext<ApiSessionValue | null>(null);

function connectionError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "The API key is invalid, expired, or not active.";
    if (error.status === 429) return "The API is rate limiting requests. Wait, then try again.";
    if (error.status === 0) return error.message;
    return `The production API could not verify this key (HTTP ${error.status}).`;
  }
  return "The production API could not be reached. Check the API URL and network.";
}

export function ApiSessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [workspace, setWorkspace] = useState<WorkspaceContext | null>(null);
  const [connectionVersion, setConnectionVersion] = useState(0);
  const [status, setStatus] = useState<ApiSessionStatus>("disconnected");
  const [error, setError] = useState("");

  const disconnect = useCallback(() => {
    queryClient.clear();
    setApiKey("");
    setWorkspace(null);
    setError("");
    setStatus("disconnected");
    setConnectionVersion((version) => version + 1);
  }, [queryClient]);

  const connect = useCallback(
    async (key: string): Promise<boolean> => {
      const cleanKey = key.trim();
      if (!cleanKey) {
        setStatus("error");
        setError("Paste a production API key to connect.");
        return false;
      }

      // Remove data from the previous tenant before validating a new key.
      queryClient.clear();
      setApiKey("");
      setWorkspace(null);
      setError("");
      setStatus("checking");
      setConnectionVersion((version) => version + 1);

      try {
        const context = await apiFetch<WorkspaceContext>("/v1/context", {
          token: cleanKey,
          cache: "no-store",
        });
        if (context.environment !== "production") {
          setStatus("error");
          setError(
            `This key is for ${context.environment}. Only production workspaces can connect here.`,
          );
          return false;
        }

        setApiKey(cleanKey);
        setWorkspace(context);
        setStatus("connected");
        setError("");
        setConnectionVersion((version) => version + 1);
        return true;
      } catch (requestError) {
        setStatus("error");
        setError(connectionError(requestError));
        return false;
      }
    },
    [queryClient],
  );

  const value = useMemo<ApiSessionValue>(
    () => ({
      apiKey,
      workspace,
      connectionVersion,
      status,
      error,
      connect,
      disconnect,
    }),
    [apiKey, workspace, connectionVersion, status, error, connect, disconnect],
  );

  return (
    <ApiSessionContext.Provider value={value}>
      {children}
    </ApiSessionContext.Provider>
  );
}

export function useApiSession(): ApiSessionValue {
  const value = useContext(ApiSessionContext);
  if (!value) {
    throw new Error("useApiSession must be used inside ApiSessionProvider");
  }
  return value;
}
