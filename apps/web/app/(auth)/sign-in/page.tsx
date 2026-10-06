import type { Metadata } from "next";
import Image from "next/image";
import { Icon } from "@/components/icons";
import { hasOidcProvider, signIn } from "../../../auth";

export const metadata: Metadata = { title: "Sign in" };
export const dynamic = "force-dynamic";

async function beginSsoSignIn() {
  "use server";
  await signIn("workspace-sso", { redirectTo: "/dashboard" });
}

export default function SignInPage() {
  return (
    <div className="auth-stage">
      <section className="auth-story">
        <h1 className="auth-headline">
          Machine payments,
          <br />
          <em>human control.</em>
        </h1>
        <div className="auth-proof">
          <div>
            <strong>Policy first</strong>
            <span>Check limits before a service is paid.</span>
          </div>
          <div>
            <strong>Human control</strong>
            <span>Keep approval decisions with your team.</span>
          </div>
          <div>
            <strong>Clear evidence</strong>
            <span>Keep payment and delivery records together.</span>
          </div>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <Image
            className="auth-logo"
            src="/PaxRelay-logo.png"
            alt="PaxRelay"
            width={200}
            height={50}
            priority
          />
          <span className="eyebrow">PaxRelay workspace</span>
          <h1>Sign in to PaxRelay</h1>
          <p>
            Sign in with your organisation&apos;s identity provider. A project
            owner must invite your verified work email before you can view data.
          </p>
          {!hasOidcProvider ? <div className="preview-note" role="note">
            <span className="preview-note-mark" aria-hidden="true">
              i
            </span>
            <p>Company sign-in is not configured for this deployment.</p>
          </div> : null}
          <form action={beginSsoSignIn}>
            <button className="auth-option" type="submit" disabled={!hasOidcProvider}>
              <span className="agent-avatar blue">SSO</span>
              <span>Continue with company SSO</span>
            </button>
          </form>
          <div className="auth-note">
            <Icon
              name="approvals"
              width={16}
              style={{ verticalAlign: "middle", marginRight: 8 }}
            />
            Your project role controls what you can view and change. Sign-in
            does not connect or grant access to payment wallets.
          </div>
        </div>
      </section>
    </div>
  );
}
