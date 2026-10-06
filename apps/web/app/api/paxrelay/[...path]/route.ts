import { SignJWT } from "jose";
import { getToken } from "next-auth/jwt";
import { NextRequest } from "next/server";

const MAX_BODY_BYTES = 1 * 1024 * 1024;
const UPSTREAM_TIMEOUT_MS = 30_000;
const TEMPLATE_SECRET_MARKERS = ["replace-me", "change-me", "changeme", "example", "placeholder"];

function errorResponse(status: number, code: string, message: string): Response {
  return Response.json(
    { error: { code, message } },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

async function readLimitedBody(request: Request): Promise<ArrayBuffer | null> {
  const declaredLength = Number(request.headers.get("content-length") ?? 0);
  if (Number.isFinite(declaredLength) && declaredLength > MAX_BODY_BYTES) return null;
  if (!request.body) return new ArrayBuffer(0);

  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_BODY_BYTES) {
        await reader.cancel();
        return null;
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body.buffer;
}

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const serverEnvironment = process.env.APP_ENV;
  const publicEnvironment = process.env.NEXT_PUBLIC_APP_ENV;
  if (serverEnvironment && publicEnvironment && serverEnvironment !== publicEnvironment) {
    return errorResponse(503, "environment_mismatch", "The web deployment environment is misconfigured.");
  }
  const appEnvironment = serverEnvironment ?? publicEnvironment ?? "development";
  const protectedDeployment = appEnvironment === "staging" || appEnvironment === "production";
  const authSecret = protectedDeployment
    ? process.env.WEB_AUTH_SECRET
    : process.env.WEB_AUTH_SECRET ?? process.env.AUTH_SECRET;
  const internalSecret = process.env.INTERNAL_DASHBOARD_AUTH_SECRET;
  const oidcIssuer = process.env.OIDC_ISSUER?.trim();
  if (!authSecret || !internalSecret || !oidcIssuer) {
    return errorResponse(503, "dashboard_auth_not_configured", "Dashboard sign-in is not configured.");
  }
  if (protectedDeployment) {
    const invalidSecret = (value: string) =>
      value.length < 40 || TEMPLATE_SECRET_MARKERS.some((marker) => value.toLowerCase().includes(marker));
    let issuerUrl: URL;
    try {
      issuerUrl = new URL(oidcIssuer);
    } catch {
      return errorResponse(503, "dashboard_auth_not_configured", "Dashboard sign-in is not configured.");
    }
    if (
      invalidSecret(authSecret) ||
      invalidSecret(internalSecret) ||
      authSecret === internalSecret ||
      authSecret === process.env.AUTH_SECRET ||
      internalSecret === process.env.AUTH_SECRET ||
      issuerUrl.protocol !== "https:" ||
      !issuerUrl.hostname ||
      issuerUrl.username ||
      issuerUrl.password ||
      issuerUrl.search ||
      issuerUrl.hash
    ) {
      return errorResponse(503, "dashboard_auth_not_configured", "Dashboard sign-in is not configured.");
    }
  }

  if (!["GET", "HEAD", "OPTIONS"].includes(request.method)) {
    const origin = request.headers.get("origin");
    if (origin !== request.nextUrl.origin) {
      return errorResponse(403, "cross_site_request", "Cross-site dashboard requests are not allowed.");
    }
  }

  let session: Awaited<ReturnType<typeof getToken>>;
  try {
    session = await getToken({ req: request, secret: authSecret });
  } catch {
    return errorResponse(401, "unauthorized", "A verified dashboard sign-in is required.");
  }
  const oidcSubject = session?.paxrelaySubject;
  const email = session?.email;
  if (
    typeof oidcSubject !== "string" ||
    typeof email !== "string" ||
    session?.paxrelayEmailVerified !== true ||
    session?.paxrelayIssuer !== oidcIssuer
  ) {
    return errorResponse(401, "unauthorized", "A verified dashboard sign-in is required.");
  }

  const { path } = await context.params;
  if (
    !Array.isArray(path) ||
    path.length === 0 ||
    path[0] !== "v1" ||
    path.some((segment) => !segment || segment === "." || segment === ".." || segment.includes("/") || segment.includes("\\"))
  ) {
    return errorResponse(404, "not_found", "The requested API route was not found.");
  }

  const projectId = request.headers.get("x-project-id");
  if (projectId && !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(projectId)) {
    return errorResponse(400, "invalid_project_id", "The selected project ID is invalid.");
  }

  const apiBase = protectedDeployment
    ? process.env.PAXRELAY_API_BASE_URL
    : process.env.PAXRELAY_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!apiBase) {
    return errorResponse(503, "api_not_configured", "The PaxRelay API URL is not configured.");
  }

  let upstreamUrl: URL;
  try {
    const base = new URL(apiBase);
    if (protectedDeployment && base.protocol !== "https:") {
      return errorResponse(503, "insecure_api_url", "Staging and production API connections require HTTPS.");
    }
    if (base.username || base.password || base.search || base.hash || base.pathname !== "/") {
      return errorResponse(503, "invalid_api_url", "The API URL must be an origin without credentials, path, or query parameters.");
    }
    upstreamUrl = new URL(`/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`, base);
  } catch {
    return errorResponse(503, "invalid_api_url", "The PaxRelay API URL is invalid.");
  }

  const bearer = await new SignJWT({
    oidc_issuer: oidcIssuer,
    email,
    email_verified: true,
    name: typeof session.name === "string" ? session.name : undefined,
  })
    .setProtectedHeader({ alg: "HS256", typ: "JWT" })
    .setIssuer("paxrelay-web")
    .setAudience("paxrelay-api")
    .setSubject(oidcSubject)
    .setIssuedAt()
    .setJti(crypto.randomUUID())
    .setExpirationTime("60s")
    .sign(new TextEncoder().encode(internalSecret));

  const clientRequestId = request.headers.get("x-request-id");
  const safeRequestId = clientRequestId && /^[A-Za-z0-9._:-]{1,128}$/.test(clientRequestId)
    ? clientRequestId
    : crypto.randomUUID();
  const headers = new Headers({
    Authorization: `Bearer ${bearer}`,
    Accept: request.headers.get("accept") ?? "application/json",
    "X-Request-ID": safeRequestId,
  });
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  if (projectId) headers.set("X-Project-ID", projectId);

  let body: ArrayBuffer | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    let limitedBody: ArrayBuffer | null;
    try {
      limitedBody = await readLimitedBody(request);
    } catch {
      return errorResponse(400, "invalid_request_body", "The request body could not be read.");
    }
    if (limitedBody === null) {
      return errorResponse(413, "request_too_large", "The request body is too large.");
    }
    body = limitedBody;
  }

  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(UPSTREAM_TIMEOUT_MS)]),
    });
  } catch {
    return errorResponse(502, "api_unavailable", "The PaxRelay API could not be reached.");
  }

  if (upstream.status >= 300 && upstream.status < 400) {
    return errorResponse(502, "api_redirect_rejected", "The PaxRelay API returned an unexpected redirect.");
  }

  const responseHeaders = new Headers({
    "Cache-Control": "no-store",
  });
  for (const name of ["content-type", "retry-after", "x-request-id", "ratelimit-limit", "ratelimit-remaining", "ratelimit-reset"]) {
    const value = upstream.headers.get(name);
    if (value) responseHeaders.set(name, value);
  }
  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
