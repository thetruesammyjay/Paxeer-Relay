"use client";
import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";
import { Icon, type IconName } from "./icons";

const GROUPS: {
  label: string;
  links: { href: Route; label: string; icon: IconName; count?: string }[];
}[] = [
  {
    label: "Operate",
    links: [
      { href: "/dashboard", label: "Overview", icon: "overview" },
      { href: "/transactions", label: "Transactions", icon: "transactions" },
      { href: "/approvals", label: "Approvals", icon: "approvals", count: "2" },
    ],
  },
  {
    label: "Configure",
    links: [
      { href: "/agents", label: "Agents", icon: "agents" },
      { href: "/policies", label: "Policies", icon: "policies" },
    ],
  },
  {
    label: "Network",
    links: [
      { href: "/providers", label: "Providers", icon: "providers" },
      { href: "/services", label: "Services", icon: "services" },
    ],
  },
  {
    label: "Evidence",
    links: [
      { href: "/receipts", label: "Receipts", icon: "receipts" },
      { href: "/analytics", label: "Analytics", icon: "analytics" },
    ],
  },
];

function Brand({ mobile = false }: { mobile?: boolean }) {
  return (
    <div className={mobile ? "mobile-brand" : "brand"}>
      <span className="brand-mark" />
      <span className="brand-name">
        Paxeer <span>Relay</span>
      </span>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/") return <>{children}</>;
  const active = (href: Route) =>
    pathname === href || pathname.startsWith(`${href}/`);
  const current =
    GROUPS.flatMap((group) => group.links).find((link) => active(link.href))
      ?.label ?? "Workspace";
  return (
    <div className="app-frame">
      <aside className="sidebar">
        <Brand />
        <div className="workspace-switch" aria-label="Current workspace">
          <span className="workspace-avatar">PL</span>
          <span className="workspace-copy">
            <strong>Pax Labs</strong>
            <span>Production workspace</span>
          </span>
          <span className="muted">⌄</span>
        </div>
        <nav aria-label="Primary navigation">
          {GROUPS.map((group) => (
            <div className="nav-group" key={group.label}>
              <div className="nav-label">{group.label}</div>
              {group.links.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`nav-link ${active(link.href) ? "active" : ""}`}
                >
                  <Icon name={link.icon} className="nav-icon" />
                  <span>{link.label}</span>
                  {link.count ? (
                    <span className="nav-count">{link.count}</span>
                  ) : null}
                </Link>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="network-card">
            <div className="network-line">
              <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <i className="pulse" />
                <strong>Relay healthy</strong>
              </span>
              <span>99.99%</span>
            </div>
            <div className="network-line" style={{ marginTop: 9 }}>
              <span>LayerX · Chain 125</span>
              <span>247 ms</span>
            </div>
          </div>
          <Link
            href="/settings"
            className={`nav-link ${active("/settings") ? "active" : ""}`}
          >
            <Icon name="settings" className="nav-icon" />
            <span>Settings</span>
          </Link>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <Brand mobile />
          <div className="crumb">
            Pax Labs&nbsp;&nbsp;/&nbsp;&nbsp;<strong>{current}</strong>
          </div>
          <div className="top-spacer" />
          <button className="command-button" type="button">
            <Icon name="search" width={14} />
            <span>Search or jump to…</span>
            <kbd>⌘ K</kbd>
          </button>
          <span className="network-pill">
            <i className="pulse" /> PAXEER MAINNET
          </span>
          <button
            className="icon-button"
            type="button"
            aria-label="Notifications"
          >
            <Icon name="bell" width={14} />
          </button>
          <div className="operator">
            <span className="operator-avatar">SJ</span>
            <span style={{ fontSize: 11, fontWeight: 650 }}>Sammy</span>
          </div>
        </header>
        <main>{children}</main>
      </div>
      <nav className="mobile-nav" aria-label="Mobile navigation">
        {[
          GROUPS[0].links[0],
          GROUPS[0].links[1],
          GROUPS[0].links[2],
          GROUPS[1].links[0],
        ].map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={active(link.href) ? "active" : ""}
          >
            <Icon name={link.icon} className="nav-icon" />
            <span>{link.label}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
}
