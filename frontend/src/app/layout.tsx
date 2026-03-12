import type { Metadata } from 'next';
import { Providers } from './providers';
import { ShopifyNavigationSync } from '@/components/ShopifyNavigationSync';
import AppBridgeProvider from '@/components/AppBridgeProvider';
import PolarisProvider from '@/components/PolarisProvider';
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
        <script src="https://cdn.shopify.com/shopifycloud/app-bridge.js" />
      </head>
      <body>
        <AppBridgeProvider>
          <ShopifyNavigationSync />
          <PolarisProvider>
            <Providers>{children}</Providers>
          </PolarisProvider>
        </AppBridgeProvider>
      </body>
    </html>
  );
}
