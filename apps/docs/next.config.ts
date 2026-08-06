import type { NextConfig } from "next";
import { createMDX } from "fumadocs-mdx/next";
import path from "node:path";

const withMDX = createMDX();

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.join(process.cwd(), "../.."),
  reactStrictMode: true,
};

export default withMDX(nextConfig);
