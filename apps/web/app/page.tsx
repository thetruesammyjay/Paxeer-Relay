import type { Metadata, Route } from "next";
import Link from "next/link";
import { MarketingFrame } from "@/components/marketing-chrome";
import { Reveal } from "@/components/reveal";

export const metadata: Metadata = {
  title: "Agent payments, with human control",
  description:
    "PaxRelay helps teams set spending rules, coordinate paid services for AI agents, and keep a clear record of each request.",
};

const requestSteps = [
  { number: "01", title: "Agent requests", detail: "A paid service" },
  { number: "02", title: "PaxRelay checks", detail: "Rules and price" },
  { number: "03", title: "Payment is verified", detail: "Through the payment flow" },
  { number: "04", title: "Provider responds", detail: "Service result" },
  { number: "05", title: "Activity is recorded", detail: "Request and receipt" },
];

const workspaces = [
  {
    number: "01",
    title: "For agent operators",
    body: "Set spending rules and follow requests, payments, and service results in one place.",
    href: "/dashboard",
    action: "Open the operator workspace",
  },
  {
    number: "02",
    title: "For service providers",
    body: "See how a provider can manage paid services and review incoming requests.",
    href: "/creator",
    action: "Open the provider workspace",
  },
  {
    number: "03",
    title: "For PaxRelay operations",
    body: "Explore the internal view for creator reviews, workspaces, and platform activity.",
    href: "/admin",
    action: "Open the operations workspace",
  },
];

export default function LandingPage() {
  return (
    <MarketingFrame>
      <main className="landing-page">
        <div className="landing-content">
        <section className="landing-hero" aria-labelledby="landing-title">
          <Reveal className="landing-hero-copy">
            <p className="landing-eyebrow">
              <span aria-hidden="true" />
              CONTROL FOR MACHINE-TO-MACHINE COMMERCE
            </p>
            <h1 id="landing-title">
              Machine payments,
              <br />
              <em>human control.</em>
            </h1>
            <p className="landing-lede">
              Give AI agents a way to use paid online services while your team
              sets the rules, checks the price, and can see what happened next.
            </p>
            <div className="landing-hero-actions">
              <Link className="landing-button landing-button-ember" href="/dashboard">
                Open your workspace <span aria-hidden="true">↗</span>
              </Link>
              <a className="landing-text-link" href="#how-it-works">
                See how a request works <span aria-hidden="true">↓</span>
              </a>
            </div>
            <p className="landing-preview-caption">
              <span className="landing-preview-dot" aria-hidden="true" />
              Live API data · Scoped to your selected project and role
            </p>
          </Reveal>

          <Reveal className="landing-art-wrap" delay={0.12}>
          <div className="landing-request-art" role="group" aria-label="Illustration of an agent request being checked and recorded">
            <div className="landing-art-glow" aria-hidden="true" />
            <div className="landing-art-topline">
              <span>ONE REQUEST · CLEAR RECORD</span>
              <span className="landing-art-tag">ILLUSTRATION</span>
            </div>
            <div className="landing-agent-request">
              <div className="landing-agent-avatar" aria-hidden="true">R</div>
              <div className="landing-agent-copy">
                <span>AGENT REQUEST</span>
                <strong>Research Runner</strong>
                <p>Find a current market snapshot</p>
              </div>
              <span className="landing-request-amount">0.024 USDX</span>
            </div>
            <div className="landing-mini-flow" aria-label="Rules, payment, service, record">
              <div className="landing-mini-step is-current">
                <span className="landing-mini-mark">01</span>
                <span>Rules</span>
              </div>
              <span className="landing-mini-connector" aria-hidden="true" />
              <div className="landing-mini-step">
                <span className="landing-mini-mark">02</span>
                <span>Payment</span>
              </div>
              <span className="landing-mini-connector" aria-hidden="true" />
              <div className="landing-mini-step">
                <span className="landing-mini-mark">03</span>
                <span>Service</span>
              </div>
              <span className="landing-mini-connector" aria-hidden="true" />
              <div className="landing-mini-step">
                <span className="landing-mini-mark">04</span>
                <span>Receipt</span>
              </div>
            </div>
            <div className="landing-art-result">
              <span className="landing-result-mark" aria-hidden="true">✓</span>
              <div>
                <strong>Every step stays connected</strong>
                <span>Policy · payment · provider response · receipt</span>
              </div>
              <span className="landing-result-label">TRACEABLE</span>
            </div>
            <p className="landing-art-footnote">
              An example of the request story PaxRelay is designed to show.
            </p>
          </div>
          </Reveal>
        </section>

        <Reveal as="section" className="landing-principles" aria-label="PaxRelay benefits">
          <div className="landing-principle">
            <span className="landing-principle-number">01 / SET THE RULES</span>
            <strong>Decide what an agent can spend.</strong>
          </div>
          <div className="landing-principle">
            <span className="landing-principle-number">02 / CHECK THE REQUEST</span>
            <strong>See the service and price before payment.</strong>
          </div>
          <div className="landing-principle">
            <span className="landing-principle-number">03 / KEEP THE EVIDENCE</span>
            <strong>Follow payment and service results together.</strong>
          </div>
        </Reveal>

        <Reveal as="section" className="landing-how" id="how-it-works" aria-labelledby="landing-how-title">
          <div className="landing-section-heading">
            <div>
              <p className="landing-eyebrow">A REQUEST, STEP BY STEP</p>
              <h2 id="landing-how-title">From request to result, with a clear record.</h2>
            </div>
            <p>
              PaxRelay coordinates the checks around a paid service call. Your
              team keeps control of its rules and payment setup.
            </p>
          </div>
          <ol className="landing-lifecycle">
            {requestSteps.map((step) => (
              <li className="landing-lifecycle-step" key={step.number}>
                <span className="landing-lifecycle-number">{step.number}</span>
                <strong>{step.title}</strong>
                <span>{step.detail}</span>
              </li>
            ))}
          </ol>
          <p className="landing-custody-note">
            PaxRelay coordinates existing wallet and payment services. It does
            not take custody of customer funds.
          </p>
        </Reveal>

        <Reveal as="section" className="landing-workspaces" id="workspaces" aria-labelledby="landing-workspaces-title">
          <div className="landing-section-heading">
            <div>
              <p className="landing-eyebrow">THREE WORKSPACES</p>
              <h2 id="landing-workspaces-title">Made for the people around each request.</h2>
            </div>
            <p>
              Sign in to load live project data. Your assigned role determines
              which records and actions are available in each workspace.
            </p>
          </div>
          <div className="landing-workspace-grid">
            {workspaces.map((workspace, index) => (
              <Reveal as="article" className="landing-workspace-card" delay={index * 0.07} key={workspace.number}>
                <span className="landing-workspace-number">{workspace.number}</span>
                <h3>{workspace.title}</h3>
                <p>{workspace.body}</p>
                <Link href={workspace.href as Route}>
                  {workspace.action} <span aria-hidden="true">↗</span>
                </Link>
              </Reveal>
            ))}
          </div>
        </Reveal>

        <Reveal as="section" className="landing-close" aria-labelledby="landing-close-title">
          <div>
            <p className="landing-eyebrow">BUILT FOR AGENT COMMERCE</p>
            <h2 id="landing-close-title">Let agents get work done.<br /><em>Keep the spending visible.</em></h2>
          </div>
          <Link className="landing-button landing-button-ember" href="/dashboard">
            Open your workspace <span aria-hidden="true">↗</span>
          </Link>
        </Reveal>
        </div>
      </main>
    </MarketingFrame>
  );
}
