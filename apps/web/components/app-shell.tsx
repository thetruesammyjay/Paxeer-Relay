"use client";

import Image from "next/image";
import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { HugeiconsIcon } from "@hugeicons/react";
import {
  Activity01Icon,
  Building01Icon,
  Home01Icon,
  Invoice01Icon,
  MoreHorizontalIcon,
  Notification03Icon,
  Package01Icon,
  Settings01Icon,
  ShieldCheckIcon,
  Store01Icon,
  UserGroupIcon,
} from "@hugeicons/core-free-icons";

type IconData = typeof Home01Icon;
type NavLink = { href: string; label: string; icon: IconData; count?: string };
type NavGroup = { label: string; links: NavLink[] };

const PAXRELAY_GROUPS: NavGroup[] = [
  {
    label: "Operate",
    links: [
      { href: "/dashboard", label: "Overview", icon: Home01Icon },
      { href: "/transactions", label: "Transactions", icon: Activity01Icon },
      {
        href: "/approvals",
        label: "Approvals",
        icon: ShieldCheckIcon,
        count: "2",
      },
    ],
  },
  {
    label: "Configure",
    links: [
      { href: "/agents", label: "Agents", icon: UserGroupIcon },
      { href: "/policies", label: "Policies", icon: Settings01Icon },
    ],
  },
  {
    label: "Network",
    links: [
      { href: "/providers", label: "Providers", icon: Store01Icon },
      { href: "/services", label: "Services", icon: Package01Icon },
    ],
  },
  {
    label: "Evidence",
    links: [
      { href: "/receipts", label: "Receipts", icon: Invoice01Icon },
      { href: "/analytics", label: "Analytics", icon: Activity01Icon },
    ],
  },
];

const ADMIN_GROUPS: NavGroup[] = [
  {
    label: "Platform",
    links: [
      { href: "/admin", label: "Overview", icon: Home01Icon },
      { href: "/admin#creators", label: "Creators", icon: UserGroupIcon },
      { href: "/admin#activity", label: "Activity", icon: Activity01Icon },
    ],
  },
  {
    label: "Controls",
    links: [
      { href: "/admin#workspaces", label: "Workspaces", icon: Building01Icon },
      { href: "/admin#health", label: "Platform health", icon: Activity01Icon },
      { href: "/admin#settings", label: "Settings", icon: Settings01Icon },
    ],
  },
];

const CREATOR_GROUPS: NavGroup[] = [
  {
    label: "Your business",
    links: [
      { href: "/creator", label: "Overview", icon: Home01Icon },
      { href: "/creator#services", label: "Services", icon: Package01Icon },
      {
        href: "/creator#requests",
        label: "Requests",
        icon: Notification03Icon,
      },
      { href: "/creator#receipts", label: "Receipts", icon: Invoice01Icon },
    ],
  },
  {
    label: "Account",
    links: [
      {
        href: "/creator#profile",
        label: "Profile & settings",
        icon: Settings01Icon,
      },
    ],
  },
];

const WORKSPACES = [
  {
    href: "/dashboard",
    label: "PaxRelay workspace",
    detail: "Monitor agent activity",
  },
  {
    href: "/admin",
    label: "Admin dashboard",
    detail: "Manage the PaxRelay platform",
  },
  {
    href: "/creator",
    label: "Creator dashboard",
    detail: "Manage your services",
  },
];

function Brand({ mobile = false }: { mobile?: boolean }) {
  return (
    <div className={mobile ? "mobile-brand" : "brand"}>
      <Image
        className="brand-logo"
        src={mobile ? "/PaxRelay-ico.png" : "/PaxRelay-logo.png"}
        alt="PaxRelay"
        width={mobile ? 32 : 160}
        height={mobile ? 32 : 40}
        priority
      />
    </div>
  );
}

function NavGlyph({ icon, size = 18 }: { icon: IconData; size?: number }) {
  return (
    <HugeiconsIcon
      icon={icon}
      size={size}
      color="currentColor"
      strokeWidth={1.7}
      aria-hidden="true"
    />
  );
}

function MobileMoreSheet({
  groups,
  settingsHref,
  workspaceLabel,
  visibleHrefs,
  onClose,
}: {
  groups: NavGroup[];
  settingsHref: string;
  workspaceLabel: string;
  visibleHrefs: string[];
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const sheetRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const previousFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      const focusable = Array.from(
        sheetRef.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
      previousFocus?.focus();
    };
  }, [onClose]);

  const visible = new Set(visibleHrefs);
  const quickLinks = groups
    .flatMap((group) => group.links)
    .filter((link) => !visible.has(link.href));

  return (
    <div className="mobile-more-overlay">
      <button
        className="mobile-more-backdrop"
        type="button"
        aria-label="Close quick actions"
        onClick={onClose}
      />
      <section
        ref={sheetRef}
        className="mobile-more-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="mobile-more-title"
      >
        <div className="mobile-sheet-grip" aria-hidden="true" />
        <header className="mobile-more-head">
          <div>
            <p className="eyebrow">{workspaceLabel}</p>
            <h2 id="mobile-more-title">Quick actions</h2>
          </div>
          <button
            ref={closeRef}
            className="mobile-more-close"
            type="button"
            aria-label="Close quick actions"
            onClick={onClose}
          >
            <span aria-hidden="true">×</span>
          </button>
        </header>

        <div className="mobile-more-grid">
          {quickLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href as Route}
              className="mobile-more-link"
              onClick={onClose}
            >
              <span className="mobile-more-icon">
                <NavGlyph icon={link.icon} size={21} />
              </span>
              <span>{link.label}</span>
            </Link>
          ))}
          {!quickLinks.some((link) =>
            link.label.toLowerCase().includes("settings"),
          ) ? (
            <Link
              href={settingsHref as Route}
              className="mobile-more-link"
              onClick={onClose}
            >
              <span className="mobile-more-icon">
                <NavGlyph icon={Settings01Icon} size={21} />
              </span>
              <span>Settings</span>
            </Link>
          ) : null}
        </div>

        <div className="mobile-workspace-switcher">
          <p className="mobile-sheet-label">Switch dashboard</p>
          <div>
            {WORKSPACES.map((workspace) => (
              <Link
                key={workspace.href}
                href={workspace.href as Route}
                onClick={onClose}
              >
                <strong>{workspace.label}</strong>
                <span>{workspace.detail}</span>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);
  const [fragment, setFragment] = useState("");
  const closeMore = useCallback(() => setMoreOpen(false), []);

  useEffect(() => {
    const readFragment = () => setFragment(window.location.hash);
    readFragment();
    window.addEventListener("hashchange", readFragment);
    return () => window.removeEventListener("hashchange", readFragment);
  }, [pathname]);

  const workspace = pathname.startsWith("/admin")
    ? "admin"
    : pathname.startsWith("/creator")
      ? "creator"
      : "paxrelay";
  if (
    pathname === "/" ||
    pathname === "/sign-in" ||
    pathname === "/how-it-works" ||
    pathname === "/for-teams" ||
    pathname === "/for-providers"
  ) {
    return <>{children}</>;
  }

  const groups =
    workspace === "admin"
      ? ADMIN_GROUPS
      : workspace === "creator"
        ? CREATOR_GROUPS
        : PAXRELAY_GROUPS;
  const workspaceName =
    workspace === "admin"
      ? "PaxRelay platform"
      : workspace === "creator"
        ? "Atlas Data Studio"
        : "Pax Labs";
  const workspaceDetail =
    workspace === "admin"
      ? "Sample admin preview"
      : workspace === "creator"
        ? "Sample creator preview"
        : "Sample workspace";
  const settingsHref =
    workspace === "admin"
      ? "/admin#settings"
      : workspace === "creator"
        ? "/creator#profile"
        : "/settings";
  const allLinks = groups.flatMap((group) => group.links);
  const isActive = (href: string) => {
    const [path, hash] = href.split("#");
    if (hash) return pathname === path && fragment === `#${hash}`;
    const matchesPath = pathname === path || pathname.startsWith(`${path}/`);
    return matchesPath && !(pathname === path && fragment.length > 0);
  };
  const current =
    pathname === "/settings"
      ? "Settings"
      : (allLinks.find((link) => isActive(link.href))?.label ?? "Overview");

  const mobileLinks =
    workspace === "admin"
      ? [
          { href: "/admin", label: "Home", icon: Home01Icon },
          { href: "/admin#creators", label: "Creators", icon: UserGroupIcon },
          { href: "/admin#activity", label: "Activity", icon: Activity01Icon },
        ]
      : workspace === "creator"
        ? [
            { href: "/creator", label: "Home", icon: Home01Icon },
            {
              href: "/creator#services",
              label: "Services",
              icon: Package01Icon,
            },
            {
              href: "/creator#requests",
              label: "Requests",
              icon: Notification03Icon,
            },
          ]
        : [
            { href: "/dashboard", label: "Home", icon: Home01Icon },
            { href: "/transactions", label: "Activity", icon: Activity01Icon },
            { href: "/approvals", label: "Approvals", icon: ShieldCheckIcon },
          ];

  return (
    <div className={`app-frame workspace-${workspace}`}>
      <aside className="sidebar">
        <Brand />
        <details className="workspace-switch">
          <summary>
            <span className="workspace-avatar">
              {workspace === "admin"
                ? "AD"
                : workspace === "creator"
                  ? "CR"
                  : "PL"}
            </span>
            <span className="workspace-copy">
              <strong>{workspaceName}</strong>
              <span>{workspaceDetail}</span>
            </span>
            <span className="workspace-chevron" aria-hidden="true">
              ⌄
            </span>
          </summary>
          <div className="workspace-menu">
            {WORKSPACES.map((item) => (
              <Link key={item.href} href={item.href as Route}>
                <strong>{item.label}</strong>
                <span>{item.detail}</span>
              </Link>
            ))}
          </div>
        </details>
        <nav aria-label="Primary navigation">
          {groups.map((group) => (
            <div className="nav-group" key={group.label}>
              <div className="nav-label">{group.label}</div>
              {group.links.map((link) => (
                <Link
                  key={link.href}
                  href={link.href as Route}
                  className={`nav-link ${isActive(link.href) ? "active" : ""}`}
                  aria-current={isActive(link.href) ? "page" : undefined}
                >
                  <NavGlyph icon={link.icon} size={17} />
                  <span>{link.label}</span>
                  {link.count ? (
                    <span className="nav-count">{link.count}</span>
                  ) : null}
                </Link>
              ))}
            </div>
          ))}
        </nav>
        {workspace === "paxrelay" ? (
          <div className="sidebar-bottom">
            <div className="network-card">
              <div className="network-line">
                <span className="network-health">
                  <i className="pulse" />
                Sample relay
              </span>
              <span>Preview</span>
            </div>
            <div className="network-line network-detail">
              <span>Demo settlement · LayerX</span>
              <span>247 ms</span>
              </div>
            </div>
            <Link
              href="/settings"
              className={`nav-link ${isActive("/settings") ? "active" : ""}`}
            >
              <NavGlyph icon={Settings01Icon} size={17} />
              <span>Settings</span>
            </Link>
          </div>
        ) : null}
      </aside>

      <div className="main-column">
        <header className="topbar">
          <Brand mobile />
          <div className="crumb">
            {workspaceName}&nbsp;&nbsp;/&nbsp;&nbsp;<strong>{current}</strong>
          </div>
          <div className="top-spacer" />
          <span className="network-pill network-demo">
            <i className="sample-mark" aria-hidden="true" />
            Sample data · View only
          </span>
          <div className="operator">
            <span className="operator-avatar">SJ</span>
            <span className="operator-name">Sammy</span>
          </div>
        </header>
        <main>{children}</main>
      </div>

      <nav className="mobile-nav" aria-label="Mobile navigation">
        {mobileLinks.map((link) => (
          <Link
            key={link.href}
            href={link.href as Route}
            className={`mobile-nav-link ${isActive(link.href) ? "active" : ""}`}
            aria-current={isActive(link.href) ? "page" : undefined}
          >
            <NavGlyph icon={link.icon} size={23} />
            <span>{link.label}</span>
          </Link>
        ))}
        <button
          className={`mobile-nav-link mobile-more-trigger ${moreOpen ? "active" : ""}`}
          type="button"
          aria-expanded={moreOpen}
          aria-haspopup="dialog"
          onClick={() => setMoreOpen(true)}
        >
          <NavGlyph icon={MoreHorizontalIcon} size={23} />
          <span>More</span>
        </button>
      </nav>
      {moreOpen ? (
        <MobileMoreSheet
          groups={groups}
          settingsHref={settingsHref}
          workspaceLabel={workspaceName}
          visibleHrefs={mobileLinks.map((link) => link.href)}
          onClose={closeMore}
        />
      ) : null}
    </div>
  );
}
