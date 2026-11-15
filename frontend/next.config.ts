import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server for the production image (frontend/Dockerfile, target prod).
  output: "standalone",
  devIndicators: false,
  allowedDevOrigins: ["127.0.0.1"],
  experimental: { cpus: 2 },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.BACKEND_URL || "http://localhost:8000"}/api/v1/:path*`,
      },
    ];
  },
};
export default nextConfig;
