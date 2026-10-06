"use client";

import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api-client";
import { useApiSession } from "@/lib/api-session";

type ProjectRole = "owner" | "admin" | "operator" | "analyst" | "viewer";

interface ProjectMember {
  id: string;
  user_id: string;
  email: string;
  display_name: string | null;
  role: ProjectRole;
  is_active: boolean;
  created_at: string;
}

const ROLE_LABELS: Record<ProjectRole, string> = {
  owner: "Owner",
  admin: "Administrator",
  operator: "Operator",
  analyst: "Analyst",
  viewer: "Read only",
};

function requestError(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "The member request failed.";
}

function formatDate(value: string): string {
  const date = new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

export function ProjectMemberManagement() {
  const session = useApiSession();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<ProjectRole>("viewer");
  const [formError, setFormError] = useState("");
  const canRead = session.workspace?.scopes.includes("project-members:read") ?? false;
  const currentRole = session.workspace?.role;
  const canWrite =
    session.workspace?.scopes.includes("project-members:write") === true &&
    (currentRole === "owner" || currentRole === "admin");
  const canGrantOwner = currentRole === "owner";
  const roles = useMemo<ProjectRole[]>(
    () => canGrantOwner
      ? ["owner", "admin", "operator", "analyst", "viewer"]
      : ["admin", "operator", "analyst", "viewer"],
    [canGrantOwner],
  );

  const members = useQuery({
    queryKey: ["project-members", session.connectionVersion],
    queryFn: ({ signal }) => apiFetch<ProjectMember[]>("/v1/project-members?limit=100", {
      token: session.apiKey,
      signal,
      cache: "no-store",
    }),
    enabled: Boolean(canRead && session.apiKey && session.workspace),
    staleTime: 10_000,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });

  const invalidate = () => queryClient.invalidateQueries({
    queryKey: ["project-members", session.connectionVersion],
  });

  const addMember = useMutation({
    mutationFn: () => apiFetch<ProjectMember>("/v1/project-members", {
      method: "POST",
      token: session.apiKey,
      body: JSON.stringify({ email: email.trim(), role }),
      cache: "no-store",
    }),
    onSuccess: async () => {
      setEmail("");
      setFormError("");
      await invalidate();
    },
    onError: (error) => setFormError(requestError(error)),
  });

  const changeRole = useMutation({
    mutationFn: ({ id, nextRole }: { id: string; nextRole: ProjectRole }) =>
      apiFetch<ProjectMember>(`/v1/project-members/${encodeURIComponent(id)}`, {
        method: "PATCH",
        token: session.apiKey,
        body: JSON.stringify({ role: nextRole }),
        cache: "no-store",
      }),
    onSuccess: invalidate,
    onError: (error) => setFormError(requestError(error)),
  });

  const revoke = useMutation({
    mutationFn: (member: ProjectMember) => {
      if (!window.confirm(`Remove ${member.email} from this project? Their active dashboard access will stop.`)) {
        throw new Error("Member removal cancelled.");
      }
      return apiFetch<void>(`/v1/project-members/${encodeURIComponent(member.id)}`, {
        method: "DELETE",
        token: session.apiKey,
        cache: "no-store",
      });
    },
    onSuccess: invalidate,
    onError: (error) => {
      if (error instanceof Error && error.message === "Member removal cancelled.") return;
      setFormError(requestError(error));
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError("");
    addMember.mutate();
  }

  return (
    <section className="card project-members-card" aria-labelledby="project-members-title">
      <header className="project-members-header">
        <div>
          <p className="eyebrow">Project access</p>
          <h2 id="project-members-title">People and roles</h2>
          <p>Access is limited to the selected project and environment.</p>
        </div>
        {members.data ? <span className="status active">{members.data.filter((member) => member.is_active).length} active</span> : null}
      </header>

      {!canRead ? (
        <p className="data-access-placeholder">Your project role does not include member-directory access.</p>
      ) : (
        <>
          {canWrite ? (
            <form className="project-member-form" onSubmit={submit}>
              <label>
                <span>Work email</span>
                <input
                  type="email"
                  autoComplete="email"
                  required
                  maxLength={320}
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="person@company.com"
                />
              </label>
              <label>
                <span>Project role</span>
                <select value={role} onChange={(event) => setRole(event.target.value as ProjectRole)}>
                  {roles.map((item) => <option key={item} value={item}>{ROLE_LABELS[item]}</option>)}
                </select>
              </label>
              <button className="button primary" type="submit" disabled={addMember.isPending || !email.trim()}>
                {addMember.isPending ? "Adding…" : "Add person"}
              </button>
              <p className="project-member-hint">The person must use this verified email with your company sign-in. Send them your organisation’s sign-in link separately.</p>
            </form>
          ) : null}

          {formError ? <p className="api-session-error" role="alert">{formError}</p> : null}
          {members.isLoading ? <p role="status">Loading project members…</p> : null}
          {members.isError ? <p className="api-session-error" role="alert">{requestError(members.error)}</p> : null}
          {members.data?.length === 0 ? <p className="data-access-placeholder">No people are assigned to this project.</p> : null}

          {members.data?.length ? (
            <div className="project-members-table-wrap">
              <table className="project-members-table">
                <thead>
                  <tr><th scope="col">Person</th><th scope="col">Role</th><th scope="col">Added</th><th scope="col"><span className="sr-only">Actions</span></th></tr>
                </thead>
                <tbody>
                  {members.data.map((member) => (
                    <tr key={member.id} className={!member.is_active ? "project-member-revoked" : undefined}>
                      <td>
                        <strong>{member.display_name || member.email}</strong>
                        {member.display_name ? <span>{member.email}</span> : null}
                      </td>
                      <td>
                        {canWrite && member.is_active ? (
                          <select
                            aria-label={`Role for ${member.email}`}
                            value={member.role}
                            disabled={changeRole.isPending || (member.role === "owner" && !canGrantOwner)}
                            onChange={(event) => changeRole.mutate({ id: member.id, nextRole: event.target.value as ProjectRole })}
                          >
                            {roles.map((item) => <option key={item} value={item}>{ROLE_LABELS[item]}</option>)}
                          </select>
                        ) : <span>{ROLE_LABELS[member.role]}</span>}
                      </td>
                      <td>{formatDate(member.created_at)}</td>
                      <td>
                        {canWrite && member.is_active ? (
                          <button className="button subtle danger-text" type="button" disabled={revoke.isPending} onClick={() => revoke.mutate(member)}>
                            Remove
                          </button>
                        ) : <span className="project-member-state">{member.is_active ? "Active" : "Removed"}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
