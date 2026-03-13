import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ['@shopify/polaris'],
  async redirects() {
    return [
      { source: '/products', destination: '/dashboard/products', permanent: false },
      { source: '/products/', destination: '/dashboard/products', permanent: false },
    ];
  },
};

export default nextConfig;
