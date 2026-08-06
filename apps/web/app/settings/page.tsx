import type { Metadata } from "next";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold">Settings</h1>
      {/* Organisation settings, API keys, members, billing — implemented in a later step */}
    </div>
  );
}
