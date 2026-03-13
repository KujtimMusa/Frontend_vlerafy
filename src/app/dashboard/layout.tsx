'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { InlineStack, Box, BlockStack } from '@shopify/polaris';
import { ShopVerbindungBanner } from '@/components/ShopVerbindungBanner';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const shop = params.get('shop');
    const shopId = params.get('shop_id');
    const host = params.get('host');
    if (shop) localStorage.setItem('shop_domain', shop);
    if (host) localStorage.setItem('shopify_host', host);
    if (shopId) {
      localStorage.setItem('shop_id', shopId);
      localStorage.setItem('current_shop_id', shopId);
    }
  }, [pathname]);

  return (
    <Box padding="400">
      <BlockStack gap="400">
        <InlineStack gap="400" blockAlign="center">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/dashboard/products">Produkte</Link>
          <Link href="/dashboard/analytics">Analysen</Link>
        </InlineStack>
        <ShopVerbindungBanner />
        <Box paddingBlockStart="200">{children}</Box>
      </BlockStack>
    </Box>
  );
}
