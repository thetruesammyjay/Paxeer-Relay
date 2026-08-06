/**
 * Health probe route for the web app itself (used by uptime checks and the
 * container orchestrator). Does not touch the backend API.
 */
export async function GET() {
  return Response.json({ status: "ok", service: "web" });
}
