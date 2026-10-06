export { auth as middleware } from "./auth";

export const config = {
  runtime: "nodejs",
  matcher: [
    "/dashboard/:path*",
    "/admin/:path*",
    "/creator/:path*",
    "/agents/:path*",
    "/approvals/:path*",
    "/analytics/:path*",
    "/policies/:path*",
    "/providers/:path*",
    "/receipts/:path*",
    "/services/:path*",
    "/settings/:path*",
    "/transactions/:path*",
  ],
};
