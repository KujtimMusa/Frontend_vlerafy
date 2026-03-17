import type { Metadata } from 'next';
import { Geist } from 'next/font/google';
import { Providers } from './providers';
import { ShopifyNavigationSync } from '@/components/ShopifyNavigationSync';
import AppBridgeProvider from '@/components/AppBridgeProvider';
import './globals.css';

const geist = Geist({
  subsets: ['latin'],
  variable: '--font-geist',
  display: 'swap',
  weight: ['400', '500', '600', '700', '800'],
});

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
    <html lang="de" suppressHydrationWarning className={geist.variable}>
      <head>
        <meta name="shopify-api-key" content={shopifyApiKey} />
        <script
          src="https://cdn.shopify.com/shopifycloud/app-bridge.js"
          data-api-key={shopifyApiKey}
        />
        <script src="https://cdn.shopify.com/shopifycloud/polaris.js" />
      </head>
      <body>
        <AppBridgeProvider>
          {/* eslint-disable @next/next/no-html-link-for-pages -- s-app-nav (BFS) requires <a> for App Bridge */}
          <s-app-nav>
            <a href="/dashboard" rel="home">Übersicht</a>
            <a href="/dashboard/products">Produkte</a>
            <a href="/dashboard/pricing">Empfehlungen</a>
            <a href="/dashboard/settings">Einstellungen</a>
          </s-app-nav>
          {/* eslint-enable @next/next/no-html-link-for-pages */}
          <ShopifyNavigationSync />
          <Providers>{children}</Providers>
        </AppBridgeProvider>
      </body>
    </html>
  );
}
