import type { Metadata } from "next";
import Link from "next/link";
import { MarketingFrame } from "@/components/marketing-chrome";
import { Reveal } from "@/components/reveal";

export const metadata: Metadata = {
  title: "For agent teams",
  description:
    "Explore how PaxRelay is designed to help teams set agent spending rules and understand each paid service request.",
};

const controls = [
  {
    number: "01",
    title: "Set the boundary",
    body: "Give each agent a spending limit and a clear list of services it can use.",
  },
  {
    number: "02",
    title: "Understand the choice",
    body: "Keep the requested service and its price close to the rule that applies.",
  },
  {
    number: "03",
    title: "Follow the outcome",
    body: "Review payment and provider response together, then see the request record.",
  },
];

export default function ForTeamsPage() {
  return (
    <MarketingFrame>
      <main className="marketing-detail">
        <section className="marketing-page-hero">
          <div className="marketing-page-copy">
            <p className="landing-eyebrow">FOR AGENT OPERATORS</p>
            <h1>
              Let agents work.
              <br />
              Keep <em>spend visible.</em>
            </h1>
            <p>
              Give autonomous software access to paid services with spending
              rules your team can understand and records you can review.
            </p>
            <div className="landing-hero-actions">
              <Link className="landing-button landing-button-ember" href="/dashboard">
                Preview the operator workspace <span aria-hidden="true">↗</span>
              </Link>
              <Link className="landing-text-link" href="/how-it-works">
                See the request flow <span aria-hidden="true">→</span>
              </Link>
            </div>
          </div>
          <div className="marketing-quote-card">
            <span className="marketing-card-index">THE OPERATOR VIEW</span>
            <p>“Was this service allowed, what did it cost, and what came back?”</p>
            <div className="marketing-quote-rule" />
            <span className="marketing-quote-foot">One request. Its policy, payment, and result.</span>
          </div>
        </section>

        <section className="marketing-section" aria-labelledby="team-controls-title">
          <div className="marketing-section-heading">
            <p className="landing-eyebrow">CLEAR CONTROLS</p>
            <h2 id="team-controls-title">Know what an agent can do before it spends.</h2>
          </div>
          <div className="marketing-feature-grid">
            {controls.map((control, index) => (
              <Reveal as="article" className="marketing-feature-card" delay={index * 0.07} key={control.number}>
                <span className="landing-workspace-number">{control.number}</span>
                <h3>{control.title}</h3>
                <p>{control.body}</p>
              </Reveal>
            ))}
          </div>
        </section>

        <Reveal as="section" className="marketing-callout">
          <div>
            <p className="landing-eyebrow">PRE-ALPHA DASHBOARD</p>
            <h2>See the operator view.</h2>
            <p>
              The current workspace is a visual preview with sample agents,
              policies, and activity. It does not yet save dashboard actions.
            </p>
          </div>
          <Link className="landing-button landing-button-ember" href="/dashboard">
            Open dashboard preview <span aria-hidden="true">↗</span>
          </Link>
        </Reveal>
      </main>
    </MarketingFrame>
  );
}
