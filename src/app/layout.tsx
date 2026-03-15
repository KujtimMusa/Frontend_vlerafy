import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { Providers } from './providers';
import { ShopifyNavigationSync } from '@/components/ShopifyNavigationSync';
import AppBridgeProvider from '@/components/AppBridgeProvider';
import './globals.css';

const inter = Inter({ subsets: ['latin'], display: 'swap' });

const shopifyApiKey =
  process.env.NEXT_PUBLIC_SHOPIFY_API_KEY ||
  process.env.NEXT_PUBLIC_SHOPIFY_CLIENT_ID ||
  '';

export const metadata: Metadata = {
  title: 'vlerafy',
  description: 'Smarte Preisoptimierung für Shopify',
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="de" suppressHydrationWarning className={inter.className}>
      <head>
        <meta name="shopify-api-key" content={shopifyApiKey} />
        <script
          src="https://cdn.shopify.com/shopifycloud/app-bridge.js"
          data-api-key={shopifyApiKey}
        />
        <link
          rel="stylesheet"
          href="https://cdn.shopify.com/shopifycloud/polaris/latest/build/esm/styles.css"
        />
        <script
          type="module"
          src="https://cdn.shopify.com/shopifycloud/polaris/latest/polaris.js"
        />
      </head>
      <body>
        <AppBridgeProvider>
          <ShopifyNavigationSync />
          <Providers>{children}</Providers>
        </AppBridgeProvider>
      </body>
    </html>
  );
}
