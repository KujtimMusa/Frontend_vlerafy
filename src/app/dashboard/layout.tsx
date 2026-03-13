'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { InlineStack, Box } from '@shopify/polaris';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const searchParams = useSearchParams();

  useEffect(() => {
    const shop = searchParams.get('shop');
    const shopId = searchParams.get('shop_id');
    const host = searchParams.get('host');
    if (typeof window !== 'undefined') {
      if (shop) localStorage.setItem('shop_domain', shop);
      if (host) localStorage.setItem('shopify_host', host);
      if (shopId) {
        localStorage.setItem('shop_id', shopId);
        localStorage.setItem('current_shop_id', shopId);
      }
    }
  }, [searchParams]);

  return (
    <Box padding="400">
      <InlineStack gap="400" blockAlign="center">
        <Link href="/dashboard">Dashboard</Link>
        <Link href="/dashboard/products">Produkte</Link>
        <Link href="/dashboard/analytics">Analysen</Link>
      </InlineStack>
      <Box paddingBlockStart="400">{children}</Box>
    </Box>
  );
}
