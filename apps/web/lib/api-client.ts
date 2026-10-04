/**
 * Typed fetch wrapper around the PaxRelay control-plane API.
 *
 * The base URL comes from NEXT_PUBLIC_API_BASE_URL (with NEXT_PUBLIC_API_URL
 * retained as a compatibility fallback); the bearer token is injected by the
 * caller.
 */

const API_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface RequestOptions extends RequestInit {
  token?: string;
  /** Parse selected JSON integer fields as strings to preserve exact precision. */
  integerFieldsAsStrings?: readonly string[];
}

function preserveJsonIntegerFields(json: string, fields: readonly string[]) {
  const targets = new Set(fields);
  let output = "";
  let index = 0;

  while (index < json.length) {
    if (json[index] !== '"') {
      output += json[index++];
      continue;
    }

    const tokenStart = index++;
    let escaped = false;
    while (index < json.length) {
      const character = json[index++];
      if (escaped) {
        escaped = false;
      } else if (character === "\\") {
        escaped = true;
      } else if (character === '"') {
        break;
      }
    }

    const token = json.slice(tokenStart, index);
    output += token;
    let key: unknown;
    try {
      key = JSON.parse(token);
    } catch {
      continue;
    }
    if (typeof key !== "string" || !targets.has(key)) continue;

    let valueStart = index;
    while (/\s/.test(json[valueStart] ?? "")) valueStart += 1;
    if (json[valueStart] !== ":") continue;
    valueStart += 1;
    while (/\s/.test(json[valueStart] ?? "")) valueStart += 1;

    let valueEnd = valueStart;
    if (json[valueEnd] === "-") valueEnd += 1;
    while (/[0-9]/.test(json[valueEnd] ?? "")) valueEnd += 1;
    if (valueEnd === valueStart || (json[valueStart] === "-" && valueEnd === valueStart + 1)) {
      continue;
    }
    if (json[valueEnd] && !/[\s,}]/.test(json[valueEnd])) continue;

    output += `${json.slice(index, valueStart)}"${json.slice(valueStart, valueEnd)}"`;
    index = valueEnd;
  }

  return output;
}

export async function apiFetch<T>(
  path: string,
  { token, headers, integerFieldsAsStrings, ...init }: RequestOptions = {},
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });

  if (!res.ok) {
    let code = "unknown";
    let message = res.statusText;
    try {
      const body = await res.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? message;
    } catch {
      /* non-JSON error body — fall back to statusText */
    }
    throw new ApiError(res.status, code, message);
  }

  if (res.status === 204) return undefined as T;

  if (integerFieldsAsStrings?.length) {
    const body = await res.text();
    return JSON.parse(preserveJsonIntegerFields(body, integerFieldsAsStrings)) as T;
  }

  return res.json() as Promise<T>;
}
