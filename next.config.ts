import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ['@shopify/polaris'],
};

export default nextConfig;
