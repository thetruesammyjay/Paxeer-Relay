import type { Metadata } from "next";

export const metadata: Metadata = { title: "Sign In" };

export default function SignInPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-center">Sign in to PaxRelay</h1>
      {/* Auth form implemented in a later step */}
      <p className="text-sm text-center text-slate-500">
        Connect your wallet or sign in with email.
      </p>
    </div>
  );
}
