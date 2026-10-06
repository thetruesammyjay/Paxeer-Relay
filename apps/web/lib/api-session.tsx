"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { signOut, useSession } from "next-auth/react";
import { ApiError, apiFetch, OIDC_SESSION_TOKEN, setDashboardProjectId } from "@/lib/api-client";

export interface WorkspaceContext {
  organisation_id: string;
  project_id: string;
  environment: "development" | "test" | "staging" | "production";
  api_key_id: string | null;
  user_id: string | null;
  role: "owner" | "admin" | "operator" | "analyst" | "viewer" | null;
  scopes: string[];
}

export interface DashboardProject {
  organisation_id: string;
  organisation_name: string;
  project_id: string;
  project_name: string;
  environment: WorkspaceContext["environment"];
  role: NonNullable<WorkspaceContext["role"]>;
}

type ApiSessionStatus = "disconnected" | "checking" | "selecting" | "connected" | "error";

interface ApiSessionValue {
  apiKey: string;
  workspace: WorkspaceContext | null;
  projects: DashboardProject[];
  connectionVersion: number;
  status: ApiSessionStatus;
  isSignedIn: boolean;
  error: string;
  connect: (key: string) => Promise<boolean>;
  selectProject: (projectId: string) => Promise<boolean>;
  disconnect: () => void;
}

const ApiSessionContext = createContext<ApiSessionValue | null>(null);

function expectedEnvironment(): WorkspaceContext["environment"] {
  const environment = process.env.NEXT_PUBLIC_APP_ENV;
  if (
    environment === "production" ||
    environment === "staging" ||
    environment === "test" ||
    environment === "development"
  ) {
    return environment;
  }
  return process.env.NODE_ENV === "production" ? "production" : "development";
}

export function dashboardRequiresSso(): boolean {
  const environment = expectedEnvironment();
  return (
    process.env.NODE_ENV === "production" ||
    environment === "production" ||
    environment === "staging"
  );
}

function connectionError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your sign-in is no longer valid. Sign in again.";
    if (error.status === 403) return error.message;
    if (error.status === 429) return "The API is rate limiting requests. Wait, then try again.";
    if (error.status === 0) return error.message;
    return `The API could not verify this workspace (HTTP ${error.status}).`;
  }
  return "The API could not be reached. Check the API URL and network.";
}

export function ApiSessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const authSession = useSession();
  const [apiKey, setApiKey] = useState("");
  const [workspace, setWorkspace] = useState<WorkspaceContext | null>(null);
  const [projects, setProjects] = useState<DashboardProject[]>([]);
  const [connectionVersion, setConnectionVersion] = useState(0);
  const [status, setStatus] = useState<ApiSessionStatus>("disconnected");
  const [error, setError] = useState("");
  const oidcInitializationAttempted = useRef(false);

  const selectProject = useCallback(
    async (projectId: string): Promise<boolean> => {
      queryClient.clear();
      setWorkspace(null);
      setError("");
      setStatus("checking");
      setDashboardProjectId(projectId);
      try {
        const context = await apiFetch<WorkspaceContext>("/v1/context", {
          token: OIDC_SESSION_TOKEN,
          cache: "no-store",
        });
        if (context.environment !== expectedEnvironment()) {
          setDashboardProjectId(null);
          setStatus("error");
          setError(`This project is for ${context.environment}; this dashboard is configured for ${expectedEnvironment()}.`);
          return false;
        }
        setApiKey(OIDC_SESSION_TOKEN);
        setWorkspace(context);
        setStatus("connected");
        setError("");
        setConnectionVersion((version) => version + 1);
        return true;
      } catch (requestError) {
        setDashboardProjectId(null);
        setStatus("error");
        setError(connectionError(requestError));
        return false;
      }
    },
    [queryClient],
  );

  useEffect(() => {
    if (authSession.status === "loading") return;
    if (authSession.status === "unauthenticated") {
      oidcInitializationAttempted.current = false;
      if (apiKey === OIDC_SESSION_TOKEN) {
        queryClient.clear();
        setApiKey("");
        setWorkspace(null);
        setProjects([]);
        setDashboardProjectId(null);
        setStatus("disconnected");
        setConnectionVersion((version) => version + 1);
      }
      return;
    }
    if (
      apiKey === OIDC_SESSION_TOKEN ||
      status === "checking" ||
      oidcInitializationAttempted.current
    ) return;

    oidcInitializationAttempted.current = true;
    let cancelled = false;
    async function loadMemberships() {
      queryClient.clear();
      setApiKey("");
      setWorkspace(null);
      setProjects([]);
      setDashboardProjectId(null);
      setError("");
      setStatus("checking");
      setConnectionVersion((version) => version + 1);
      try {
        const rows = await apiFetch<DashboardProject[]>("/v1/auth/projects", {
          token: OIDC_SESSION_TOKEN,
          cache: "no-store",
        });
        if (cancelled) return;
        const available = rows.filter((row) => row.environment === expectedEnvironment());
        setProjects(available);
        if (available.length === 0) {
          setStatus("error");
          setError("Your account has no project access for this environment. Ask a project owner to invite you.");
          return;
        }
        if (available.length === 1) {
          await selectProject(available[0].project_id);
          return;
        }
        setStatus("selecting");
      } catch (requestError) {
        if (cancelled) return;
        setStatus("error");
        setError(connectionError(requestError));
      }
    }
    void loadMemberships();
    return () => {
      cancelled = true;
    };
  }, [authSession.status, apiKey, queryClient, selectProject, status]);

  const disconnect = useCallback(() => {
    const usedOidc = apiKey === OIDC_SESSION_TOKEN || authSession.status === "authenticated";
    queryClient.clear();
    setApiKey("");
    setWorkspace(null);
    setProjects([]);
    setDashboardProjectId(null);
    setError("");
    setStatus("disconnected");
    setConnectionVersion((version) => version + 1);
    if (usedOidc) void signOut({ redirectTo: "/sign-in" });
  }, [apiKey, authSession.status, queryClient]);

  const connect = useCallback(
    async (key: string): Promise<boolean> => {
      const cleanKey = key.trim();
      if (!cleanKey) {
        setStatus("error");
        setError("Paste an API key to connect.");
        return false;
      }
      if (dashboardRequiresSso()) {
        setStatus("error");
        setError("Staging and production dashboards require team sign-in. API keys are for service integrations.");
        return false;
      }

      queryClient.clear();
      setApiKey("");
      setWorkspace(null);
      setProjects([]);
      setDashboardProjectId(null);
      setError("");
      setStatus("checking");
      setConnectionVersion((version) => version + 1);
      try {
        const context = await apiFetch<WorkspaceContext>("/v1/context", {
          token: cleanKey,
          cache: "no-store",
        });
        if (context.environment !== expectedEnvironment()) {
          setStatus("error");
          setError(`This key is for ${context.environment}; this dashboard is configured for ${expectedEnvironment()}.`);
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
      projects,
      connectionVersion,
      status,
      isSignedIn: authSession.status === "authenticated",
      error,
      connect,
      selectProject,
      disconnect,
    }),
    [apiKey, workspace, projects, connectionVersion, status, authSession.status, error, connect, selectProject, disconnect],
  );

  return <ApiSessionContext.Provider value={value}>{children}</ApiSessionContext.Provider>;
}

export function useApiSession(): ApiSessionValue {
  const value = useContext(ApiSessionContext);
  if (!value) throw new Error("useApiSession must be used inside ApiSessionProvider");
  return value;
}
