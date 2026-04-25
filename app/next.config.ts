import type { NextConfig } from "next";

// Standalone output bakes a thin server.js + needed node_modules under
// .next/standalone — production Dockerfile copies this for a small image.
const config: NextConfig = {
  output: "standalone",
  // Caddy in front handles compression + headers; Next does not need to.
  poweredByHeader: false,
  reactStrictMode: true,
};

export default config;
