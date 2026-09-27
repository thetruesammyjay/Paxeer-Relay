import type { ReactNode } from "react";
import Image from "next/image";
import Link from "next/link";

const publicLinks = [
  { href: "/how-it-works", label: "How it works" },
  { href: "/for-teams", label: "For teams" },
  { href: "/for-providers", label: "For providers" },
] as const;

function MarketingHeader() {
  return (
    <header className="landing-header">
      <div className="landing-header-inner">
        <Link className="landing-brand" href="/" aria-label="PaxRelay home">
          <Image
            src="/PaxRelay-logo.png"
            alt="PaxRelay"
            width={160}
            height={40}
            priority
          />
        </Link>
        <nav className="landing-nav" aria-label="Main navigation">
          {publicLinks.map((link) => (
            <Link href={link.href} key={link.href}>
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="landing-header-actions">
          <Link className="landing-signin" href="/sign-in">
            Sign in
          </Link>
          <Link className="landing-button landing-button-dark" href="/dashboard">
            <span className="landing-cta-desktop">Explore the demo</span>
            <span className="landing-cta-mobile">Demo</span>
            <span aria-hidden="true">↗</span>
          </Link>
        </div>
      </div>
    </header>
  );
}

function MarketingFooter() {
  return (
    <footer className="landing-footer">
      <Link className="landing-footer-brand" href="/" aria-label="PaxRelay home">
        <Image src="/PaxRelay-ico.png" alt="" width={26} height={26} />
        <strong>PaxRelay</strong>
      </Link>
      <p>An independent developer project for agent-to-service payments on Paxeer Network.</p>
      <Link href="/sign-in">Sign-in preview</Link>
    </footer>
  );
}

export function MarketingFrame({ children }: { children: ReactNode }) {
  return (
    <div className="public-site">
      <MarketingHeader />
      {children}
      <MarketingFooter />
    </div>
  );
}
