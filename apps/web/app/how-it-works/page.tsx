import type { Metadata } from "next";
import Link from "next/link";
import { MarketingFrame } from "@/components/marketing-chrome";
import { Reveal } from "@/components/reveal";

export const metadata: Metadata = {
  title: "How it works",
  description:
    "See how PaxRelay is designed to connect an agent request, spending rules, payment confirmation, a provider response, and a receipt.",
};

const stages = [
  {
    number: "01",
    title: "An agent asks for a service",
    body: "The request names the work the agent needs and the service it wants to use.",
  },
  {
    number: "02",
    title: "Rules and price are checked",
    body: "The request can be compared with the team's spending limit and service permissions before payment proceeds.",
  },
  {
    number: "03",
    title: "The payment is confirmed",
    body: "PaxRelay coordinates with the configured wallet and payment flow. Funds stay under customer control.",
  },
  {
    number: "04",
    title: "The provider returns a result",
    body: "A payment and a successful service response are separate facts, so both need a clear record.",
  },
  {
    number: "05",
    title: "The request story is recorded",
    body: "The receipt brings together the request, payment, provider, and response observed by PaxRelay.",
  },
];

export default function HowItWorksPage() {
  return (
    <MarketingFrame>
      <main className="marketing-detail">
        <section className="marketing-page-hero">
          <div className="marketing-page-copy">
            <p className="landing-eyebrow">A REQUEST, STEP BY STEP</p>
            <h1>
              From request
              <br />
              to <em>receipt.</em>
            </h1>
            <p>
              PaxRelay is designed to keep the important parts of a paid
              service call connected, from the agent&apos;s request to the
              provider&apos;s response.
            </p>
            <div className="landing-hero-actions">
              <Link className="landing-button landing-button-ember" href="/dashboard">
                Explore the product preview <span aria-hidden="true">↗</span>
              </Link>
              <Link className="landing-text-link" href="/for-teams">
                For agent teams <span aria-hidden="true">→</span>
              </Link>
            </div>
          </div>
          <div className="marketing-flow-card" aria-label="Request flow overview">
            <div className="marketing-flow-card-head">
              <span>THE REQUEST PATH</span>
              <span className="landing-art-tag">PRODUCT DESIGN</span>
            </div>
            <div className="marketing-flow-agent">
              <span className="landing-agent-avatar" aria-hidden="true">A</span>
              <span><small>AGENT</small><strong>Needs a paid service</strong></span>
            </div>
            <div className="marketing-flow-track" aria-hidden="true">
              <span /><span /><span /><span />
            </div>
            <div className="marketing-flow-outcome">
              <strong>One view of the whole request</strong>
              <span>Rules · payment · provider result · receipt</span>
            </div>
          </div>
        </section>

        <section className="marketing-section" aria-labelledby="request-steps-title">
          <div className="marketing-section-heading">
            <p className="landing-eyebrow">FIVE MOMENTS</p>
            <h2 id="request-steps-title">A useful record tells the whole story.</h2>
          </div>
          <ol className="marketing-step-grid">
            {stages.map((stage, index) => (
              <Reveal as="li" className="marketing-step-card" delay={index * 0.055} key={stage.number}>
                <span className="landing-lifecycle-number">{stage.number}</span>
                <strong>{stage.title}</strong>
                <p>{stage.body}</p>
              </Reveal>
            ))}
          </ol>
          <p className="landing-custody-note">
            A receipt records what PaxRelay observed. It does not prove that a
            provider&apos;s answer was correct.
          </p>
        </section>

        <Reveal as="section" className="marketing-callout">
          <div>
            <p className="landing-eyebrow">CURRENT STATUS</p>
            <h2>This is an early product preview.</h2>
            <p>
              The dashboards use example information. Production integrations
              and end-to-end payment workflows are still being built.
            </p>
          </div>
          <Link className="landing-button landing-button-ember" href="/sign-in">
            Open sign-in preview <span aria-hidden="true">↗</span>
          </Link>
        </Reveal>
      </main>
    </MarketingFrame>
  );
}
