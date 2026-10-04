"use client";

import { useState, type FormEvent } from "react";
import type { PolicyCreateInput, PolicyMoney } from "@/hooks/use-policies";
import { createPolicy } from "@/hooks/use-policies";
import { ApiError } from "@/lib/api-client";

interface PolicyCreateFormProps {
  apiKey: string;
  onCreated: () => void;
}

function parseMoney(value: string): PolicyMoney | null {
  const amount = value.trim();
  if (!amount) return null;
  if (!/^\d+(?:\.\d{1,6})?$/.test(amount)) {
    throw new Error("Enter a non-negative USDX amount with up to 6 decimal places.");
  }
  const [whole, fraction = ""] = amount.split(".");
  if (whole.length > 72) {
    throw new Error("The amount is too large to store as a policy limit.");
  }
  const atomic = BigInt(whole) * 1_000_000n + BigInt(fraction.padEnd(6, "0"));
  if (atomic.toString().length > 78) {
    throw new Error("The amount is too large to store as a policy limit.");
  }
  return {
    amount_atomic: atomic.toString(),
    currency: "USDX",
    decimals: 6,
  };
}

function parseList(value: string) {
  return [...new Set(value.split(/[\n,]/).map((item) => item.trim()).filter(Boolean))];
}

function createErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "The API key was not accepted. Check it and try again.";
    if (error.status === 403) return "This key needs policies:write access to create policies.";
    if (error.status === 422) return "The policy contains an invalid capability, amount, mode, or provider entry.";
    return `Policy creation failed (HTTP ${error.status}). Try again shortly.`;
  }
  if (error instanceof Error) return error.message;
  return "The API could not be reached. Check that it is running and try again.";
}

export function PolicyCreateForm({ apiKey, onCreated }: PolicyCreateFormProps) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [mode, setMode] = useState<PolicyCreateInput["mode"]>("enforce");
  const [maximumPerCall, setMaximumPerCall] = useState("");
  const [dailyBudget, setDailyBudget] = useState("");
  const [monthlyBudget, setMonthlyBudget] = useState("");
  const [approvalThreshold, setApprovalThreshold] = useState("");
  const [allowedCapabilities, setAllowedCapabilities] = useState("");
  const [allowedProviders, setAllowedProviders] = useState("");
  const [blockedProviders, setBlockedProviders] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSuccessMessage("");
    try {
      const input: PolicyCreateInput = {
        name: name.trim(),
        description: description.trim() || null,
        mode,
        maximum_per_call: parseMoney(maximumPerCall),
        daily_budget: parseMoney(dailyBudget),
        monthly_budget: parseMoney(monthlyBudget),
        approval_threshold: parseMoney(approvalThreshold),
        allowed_capabilities: parseList(allowedCapabilities),
        allowed_providers: parseList(allowedProviders),
        blocked_providers: parseList(blockedProviders),
      };
      const created = await createPolicy(apiKey, input);
      setName("");
      setDescription("");
      setMaximumPerCall("");
      setDailyBudget("");
      setMonthlyBudget("");
      setApprovalThreshold("");
      setAllowedCapabilities("");
      setAllowedProviders("");
      setBlockedProviders("");
      setOpen(false);
      setSuccessMessage(`Created “${created.name}”.`);
      onCreated();
    } catch (submitError) {
      setError(createErrorMessage(submitError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="policy-create-section">
      <button
        className="button primary"
        type="button"
        aria-expanded={open}
        onClick={() => {
          setError("");
          setSuccessMessage("");
          setOpen((current) => !current);
        }}
      >
        {open ? "Close policy form" : "Create policy"}
      </button>
      {successMessage ? <p className="status active" role="status">{successMessage}</p> : null}
      {open ? (
        <section className="card policy-create-card">
          <header className="card-head">
            <div>
              <h2 className="card-title">New spending policy</h2>
              <p className="card-description">
                Set exact USDX limits and optional capability or provider boundaries.
                Empty allow lists mean no restriction.
              </p>
            </div>
          </header>
          <form className="policy-create-form" onSubmit={submit}>
            <label className="policy-form-field">
              <span>Policy name</span>
              <input
                className="search"
                required
                maxLength={128}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Research team daily guardrail"
              />
            </label>
            <label className="policy-form-field">
              <span>Mode</span>
              <select
                className="search"
                value={mode}
                onChange={(event) =>
                  setMode(event.target.value as PolicyCreateInput["mode"])
                }
              >
                <option value="observe">Observe</option>
                <option value="warn">Warn</option>
                <option value="enforce">Enforce</option>
              </select>
            </label>
            <label className="policy-form-field policy-form-wide">
              <span>Description</span>
              <input
                className="search"
                maxLength={512}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What this policy controls"
              />
            </label>
            <label className="policy-form-field">
              <span>Maximum per call (USDX)</span>
              <input
                className="search"
                inputMode="decimal"
                maxLength={80}
                value={maximumPerCall}
                onChange={(event) => setMaximumPerCall(event.target.value)}
                placeholder="No limit"
              />
            </label>
            <label className="policy-form-field">
              <span>Daily budget (USDX)</span>
              <input
                className="search"
                inputMode="decimal"
                maxLength={80}
                value={dailyBudget}
                onChange={(event) => setDailyBudget(event.target.value)}
                placeholder="No limit"
              />
            </label>
            <label className="policy-form-field">
              <span>Monthly budget (USDX)</span>
              <input
                className="search"
                inputMode="decimal"
                maxLength={80}
                value={monthlyBudget}
                onChange={(event) => setMonthlyBudget(event.target.value)}
                placeholder="No limit"
              />
            </label>
            <label className="policy-form-field">
              <span>Require approval from (USDX)</span>
              <input
                className="search"
                inputMode="decimal"
                maxLength={80}
                value={approvalThreshold}
                onChange={(event) => setApprovalThreshold(event.target.value)}
                placeholder="No threshold"
              />
            </label>
            <p className="policy-form-hint policy-form-wide">
              Amounts allow up to 6 decimal places. Enter values in USDX; the
              dashboard converts them to exact atomic units before saving.
            </p>
            <label className="policy-form-field">
              <span>Allowed capabilities</span>
              <textarea
                className="search"
                rows={3}
                value={allowedCapabilities}
                onChange={(event) => setAllowedCapabilities(event.target.value)}
                placeholder={"research.*\nweb.search"}
              />
            </label>
            <label className="policy-form-field">
              <span>Allowed provider IDs</span>
              <textarea
                className="search"
                rows={3}
                value={allowedProviders}
                onChange={(event) => setAllowedProviders(event.target.value)}
                placeholder="Leave empty to allow all providers"
              />
            </label>
            <label className="policy-form-field">
              <span>Blocked provider IDs</span>
              <textarea
                className="search"
                rows={3}
                value={blockedProviders}
                onChange={(event) => setBlockedProviders(event.target.value)}
                placeholder="Optional"
              />
            </label>
            {error ? (
              <p className="form-error policy-form-wide" role="alert">
                {error}
              </p>
            ) : null}
            <div className="page-actions policy-form-wide">
              <button className="button primary" type="submit" disabled={busy}>
                {busy ? "Creating policy…" : "Save policy"}
              </button>
            </div>
          </form>
        </section>
      ) : null}
    </section>
  );
}
