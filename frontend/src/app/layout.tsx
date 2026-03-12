import type { Metadata } from 'next';
import Script from 'next/script';
import { Providers } from './providers';
import { ShopifyNavigationSync } from '@/components/ShopifyNavigationSync';
import './globals.css';

const shopifyApiKey =
  process.env.NEXT_PUBLIC_SHOPIFY_API_KEY ||
  process.env.NEXT_PUBLIC_SHOPIFY_CLIENT_ID ||
  '';

export const metadata: Metadata = {
  title: 'Kujtims Plan - Vlerafy V3',
  description: 'KI-Preisoptimierung für Shopify',
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="de" suppressHydrationWarning>
      <head>
        <meta name="shopify-api-key" content={shopifyApiKey} />
        <Script
          src="https://cdn.shopify.com/shopifycloud/app-bridge.js"
          strategy="beforeInteractive"
        />
        <Script
          src="https://cdn.shopify.com/shopifycloud/polaris.js"
          strategy="beforeInteractive"
        />
      </head>
      <body>
        <ShopifyNavigationSync />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
