import type { Metadata } from "next";
import { Icon } from "@/components/icons";
export const metadata: Metadata = { title: "Sign in" };
export default function SignInPage() {
  return (
    <div className="auth-stage">
      <section className="auth-story">
        <div className="brand" style={{ padding: 0 }}>
          <span className="brand-mark" />
          <span className="brand-name" style={{ color: "white" }}>
            Paxeer <span>Relay</span>
          </span>
        </div>
        <h1 className="auth-headline">
          Machine payments,
          <br />
          <em>human control.</em>
        </h1>
        <div className="auth-proof">
          <div>
            <strong>99.99%</strong>
            <span>relay availability</span>
          </div>
          <div>
            <strong>247 ms</strong>
            <span>median route time</span>
          </div>
          <div>
            <strong>100%</strong>
            <span>completed calls receipted</span>
          </div>
        </div>
      </section>
      <section className="auth-panel">
        <div className="auth-card">
          <span className="eyebrow">Production control plane</span>
          <h1>Enter your workspace</h1>
          <p>
            Connect the identity that controls your agents. Signing in grants no
            spending authority.
          </p>
          <button className="auth-option">
            <span className="agent-avatar orange">PX</span>Continue with Paxeer
            Wallet<span>→</span>
          </button>
          <button className="auth-option">
            <span className="agent-avatar">0x</span>Connect an EVM wallet
            <span>→</span>
          </button>
          <button className="auth-option">
            <span className="agent-avatar blue">SSO</span>Continue with SSO
            <span>→</span>
          </button>
          <div className="auth-note">
            <Icon
              name="approvals"
              width={13}
              style={{ verticalAlign: "middle", marginRight: 6 }}
            />
            Wallet connection is read-only. Policies and approvals remain
            independently enforced.
          </div>
        </div>
      </section>
    </div>
  );
}
