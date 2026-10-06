import type { Metadata } from "next";
import Link from "next/link";
import { MarketingFrame } from "@/components/marketing-chrome";
import { Reveal } from "@/components/reveal";

export const metadata: Metadata = {
  title: "For service providers",
  description:
    "Learn how PaxRelay is designed to help online service providers publish paid services for AI agents.",
};

const providerSteps = [
  {
    number: "01",
    title: "Describe your service",
    body: "Show agents what the service does and what a request costs.",
  },
  {
    number: "02",
    title: "Receive a request",
    body: "An agent can choose a service that fits its task and spending rules.",
  },
  {
    number: "03",
    title: "Return a result",
    body: "Keep the provider response distinct from payment confirmation.",
  },
  {
    number: "04",
    title: "Review the record",
    body: "Follow the request, payment evidence, and response in one place.",
  },
];

export default function ForProvidersPage() {
  return (
    <MarketingFrame>
      <main className="marketing-detail">
        <section className="marketing-page-hero">
          <div className="marketing-page-copy">
            <p className="landing-eyebrow">FOR SERVICE PROVIDERS</p>
            <h1>
              Make your service
              <br />
              ready for <em>agents.</em>
            </h1>
            <p>
              PaxRelay is being built to help online services describe their
              offer, receive machine-to-machine requests, and keep a useful
              record of each result.
            </p>
            <div className="landing-hero-actions">
              <Link className="landing-button landing-button-ember" href="/creator">
                Open the provider workspace <span aria-hidden="true">↗</span>
              </Link>
              <Link className="landing-text-link" href="/how-it-works">
                See the request flow <span aria-hidden="true">→</span>
              </Link>
            </div>
          </div>
          <div className="marketing-provider-card">
            <div className="marketing-provider-art" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <span className="marketing-card-index">SERVICE RESPONSE</span>
            <strong>Useful work, clearly recorded.</strong>
            <p>Keep the service result connected to the request that produced it.</p>
          </div>
        </section>

        <section className="marketing-section" aria-labelledby="provider-steps-title">
          <div className="marketing-section-heading">
            <p className="landing-eyebrow">A PROVIDER&apos;S PATH</p>
            <h2 id="provider-steps-title">From service listing to request record.</h2>
          </div>
          <ol className="marketing-feature-grid marketing-provider-grid">
            {providerSteps.map((step, index) => (
              <Reveal as="li" className="marketing-feature-card" delay={index * 0.06} key={step.number}>
                <span className="landing-workspace-number">{step.number}</span>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </Reveal>
            ))}
          </ol>
        </section>

        <Reveal as="section" className="marketing-callout">
          <div>
            <p className="landing-eyebrow">LIVE PROJECT RECORDS</p>
            <h2>Explore the provider dashboard.</h2>
            <p>
              The creator workspace reads live services, transactions, and
              receipts from the selected project. Provider-specific onboarding
              and self-service payment setup are still being built.
            </p>
          </div>
          <Link className="landing-button landing-button-ember" href="/creator">
            Open the provider workspace <span aria-hidden="true">↗</span>
          </Link>
        </Reveal>
      </main>
    </MarketingFrame>
  );
}
