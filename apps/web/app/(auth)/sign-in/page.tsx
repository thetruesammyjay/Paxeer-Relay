import type { Metadata } from "next";
import Image from "next/image";
import { Icon } from "@/components/icons";

export const metadata: Metadata = { title: "Sign in" };

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
            Choose how your team will sign in. These identity providers are not
            connected in this preview.
          </p>
          <div className="preview-note" role="note">
            <span className="preview-note-mark" aria-hidden="true">
              i
            </span>
            <p>Sign-in is a visual preview. No account will be connected.</p>
          </div>
          <button className="auth-option" type="button" disabled>
            <span className="agent-avatar orange">PX</span>
            <span>Continue with Paxeer Wallet</span>
          </button>
          <button className="auth-option" type="button" disabled>
            <span className="agent-avatar">0x</span>
            <span>Connect an EVM wallet</span>
          </button>
          <button className="auth-option" type="button" disabled>
            <span className="agent-avatar blue">SSO</span>
            <span>Continue with SSO</span>
          </button>
          <div className="auth-note">
            <Icon
              name="approvals"
              width={16}
              style={{ verticalAlign: "middle", marginRight: 8 }}
            />
            Connecting a wallet does not give PaxRelay control of its funds.
            Policies and approvals remain separate.
          </div>
        </div>
      </section>
    </div>
  );
}
