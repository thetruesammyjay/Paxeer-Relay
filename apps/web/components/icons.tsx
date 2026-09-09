import type { SVGProps } from "react";

export type IconName =
  | "overview"
  | "transactions"
  | "approvals"
  | "agents"
  | "policies"
  | "providers"
  | "services"
  | "receipts"
  | "analytics"
  | "settings"
  | "search"
  | "bell"
  | "plus"
  | "arrow"
  | "filter"
  | "check"
  | "activity";

export function Icon({
  name,
  ...props
}: SVGProps<SVGSVGElement> & { name: IconName }) {
  const paths: Record<IconName, React.ReactNode> = {
    overview: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="4" rx="1.5" />
        <rect x="14" y="11" width="7" height="10" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
      </>
    ),
    transactions: (
      <>
        <path d="M4 7h14l-3-3" />
        <path d="M18 17H4l3 3" />
      </>
    ),
    approvals: (
      <>
        <path d="M12 3 4.5 6.5v5.2c0 4.4 3.1 7.4 7.5 9.3 4.4-1.9 7.5-4.9 7.5-9.3V6.5L12 3Z" />
        <path d="m8.8 12 2.1 2.1 4.6-4.7" />
      </>
    ),
    agents: (
      <>
        <circle cx="12" cy="8" r="3" />
        <path d="M5 20v-2.5A4.5 4.5 0 0 1 9.5 13h5a4.5 4.5 0 0 1 4.5 4.5V20" />
        <path d="M4 8h2M18 8h2" />
      </>
    ),
    policies: (
      <>
        <path d="M5 4h14v16H5z" />
        <path d="M8 8h8M8 12h5M8 16h7" />
      </>
    ),
    providers: (
      <>
        <path d="M4 7.5 12 3l8 4.5v9L12 21l-8-4.5Z" />
        <path d="m4 7.5 8 4.5 8-4.5M12 12v9" />
      </>
    ),
    services: (
      <>
        <path d="M12 3v4M12 17v4M3 12h4M17 12h4" />
        <circle cx="12" cy="12" r="5" />
      </>
    ),
    receipts: (
      <>
        <path d="M6 3h12v18l-3-2-3 2-3-2-3 2Z" />
        <path d="M9 8h6M9 12h6M9 16h3" />
      </>
    ),
    analytics: (
      <>
        <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1" />
      </>
    ),
    search: (
      <>
        <circle cx="11" cy="11" r="6" />
        <path d="m16 16 4 4" />
      </>
    ),
    bell: (
      <>
        <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" />
      </>
    ),
    plus: (
      <>
        <path d="M12 5v14M5 12h14" />
      </>
    ),
    arrow: (
      <>
        <path d="M5 12h14M14 7l5 5-5 5" />
      </>
    ),
    filter: (
      <>
        <path d="M4 6h16M7 12h10M10 18h4" />
      </>
    ),
    check: (
      <>
        <path d="m5 12 4 4L19 6" />
      </>
    ),
    activity: (
      <>
        <path d="M3 12h4l2-6 4 12 2-6h6" />
      </>
    ),
  };
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}
