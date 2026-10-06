import NextAuth from "next-auth";
import type { Provider } from "next-auth/providers";

const issuer = process.env.OIDC_ISSUER?.trim();
const clientId = process.env.OIDC_CLIENT_ID?.trim();
const clientSecret = process.env.OIDC_CLIENT_SECRET;
const webSecret = process.env.WEB_AUTH_SECRET;
const internalSecret = process.env.INTERNAL_DASHBOARD_AUTH_SECRET;
const serverEnvironment = process.env.APP_ENV;
const publicEnvironment = process.env.NEXT_PUBLIC_APP_ENV;
if (serverEnvironment && publicEnvironment && serverEnvironment !== publicEnvironment) {
  throw new Error("APP_ENV and NEXT_PUBLIC_APP_ENV must match in the web deployment.");
}
const appEnvironment = serverEnvironment ?? publicEnvironment ?? "development";
const providers: Provider[] = [];
const templateSecretMarkers = ["replace-me", "change-me", "changeme", "example", "placeholder"];

function isStrongSecret(value: string | undefined): value is string {
  return Boolean(
    value &&
      value.length >= 40 &&
      !templateSecretMarkers.some((marker) => value.toLowerCase().includes(marker)),
  );
}

if (issuer && clientId && clientSecret) {
  providers.push({
    id: "workspace-sso",
    name: "Company SSO",
    type: "oidc",
    issuer,
    clientId,
    clientSecret,
    authorization: { params: { scope: "openid email profile" } },
  });
}

const isProtectedDeployment = appEnvironment === "production" || appEnvironment === "staging";

if (isProtectedDeployment) {
  if (!issuer || !clientId || !clientSecret) {
    throw new Error("OIDC_ISSUER, OIDC_CLIENT_ID, and OIDC_CLIENT_SECRET are required in staging and production.");
  }
  if (!isStrongSecret(webSecret)) {
    throw new Error("WEB_AUTH_SECRET must be a non-template secret with at least 40 characters in staging and production.");
  }
  if (!isStrongSecret(internalSecret)) {
    throw new Error("INTERNAL_DASHBOARD_AUTH_SECRET must be a non-template secret with at least 40 characters in staging and production.");
  }
  if (webSecret === internalSecret) {
    throw new Error("WEB_AUTH_SECRET and INTERNAL_DASHBOARD_AUTH_SECRET must be different secrets.");
  }
  if (webSecret === process.env.AUTH_SECRET) {
    throw new Error("WEB_AUTH_SECRET must be different from the API AUTH_SECRET.");
  }
}

export const hasOidcProvider = providers.length > 0;

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers,
  secret: webSecret ?? process.env.AUTH_SECRET,
  trustHost: true,
  session: { strategy: "jwt", maxAge: 8 * 60 * 60 },
  pages: { signIn: "/sign-in" },
  callbacks: {
    jwt({ token, profile }) {
      if (profile) {
        const claims = profile as Record<string, unknown>;
        if (typeof claims.sub === "string") token.paxrelaySubject = claims.sub;
        token.paxrelayIssuer = issuer ?? "";
        token.paxrelayEmailVerified = claims.email_verified === true;
      }
      return token;
    },
    authorized({ auth: session }) {
      if (!isProtectedDeployment) return true;
      // Check a concrete session field. Auth.js configuration failures can
      // otherwise surface as a truthy error object in older runtimes.
      return typeof session?.user?.email === "string" && session.user.email.length > 0;
    },
  },
});
