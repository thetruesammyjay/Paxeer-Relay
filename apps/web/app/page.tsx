import { redirect } from "next/navigation";

/**
 * Marketing root — redirect signed-in users straight to the dashboard.
 * The actual homepage content lives in app/(marketing)/page.tsx when
 * that route group is added.
 */
export default function Home() {
  redirect("/dashboard");
}
