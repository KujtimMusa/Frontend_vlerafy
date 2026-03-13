'use client';

import { useEffect, useMemo } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { InlineStack, Box, BlockStack } from '@shopify/polaris';
import { ShopVerbindungBanner } from '@/components/ShopVerbindungBanner';

/** Shop/Host aus URL oder localStorage – für Link-Preserve */
function useShopParams(): { shop: string; host: string; shopId: string; idToken: string } {
  const searchParams = useSearchParams();
  const shop = searchParams.get('shop') ?? (typeof window !== 'undefined' ? localStorage.getItem('shop_domain') : null) ?? '';
  const host = searchParams.get('host') ?? (typeof window !== 'undefined' ? localStorage.getItem('shopify_host') : null) ?? '';
  const shopId = searchParams.get('shop_id') ?? (typeof window !== 'undefined' ? localStorage.getItem('current_shop_id') : null) ?? '';
  const idToken = searchParams.get('id_token') ?? '';
  return { shop, host, shopId, idToken };
}

export function DashboardNav({ children }: { children: React.ReactNode }) {
  const { shop, host, shopId, idToken } = useShopParams();

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (shop) localStorage.setItem('shop_domain', shop);
    if (host) localStorage.setItem('shopify_host', host);
    if (shopId) {
      localStorage.setItem('shop_id', shopId);
      localStorage.setItem('current_shop_id', shopId);
    }
  }, [shop, host, shopId]);

  const query = useMemo(() => {
    const p = new URLSearchParams();
    if (shop) p.set('shop', shop);
    if (host) p.set('host', host);
    if (shopId) p.set('shop_id', shopId);
    if (idToken) p.set('id_token', idToken);
    return p.toString();
  }, [shop, host, shopId, idToken]);

  const linkSuffix = query ? `?${query}` : '';

  return (
    <Box padding="400">
      <BlockStack gap="400">
        <InlineStack gap="400" blockAlign="center">
          <Link href={`/dashboard${linkSuffix}`}>Dashboard</Link>
          <Link href={`/dashboard/products${linkSuffix}`}>Produkte</Link>
          <Link href={`/dashboard/analytics${linkSuffix}`}>Analysen</Link>
        </InlineStack>
        <ShopVerbindungBanner />
        <Box paddingBlockStart="200">{children}</Box>
      </BlockStack>
    </Box>
  );
}
