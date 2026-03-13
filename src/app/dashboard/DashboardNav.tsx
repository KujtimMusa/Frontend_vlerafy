'use client';

import { useEffect, useMemo } from 'react';
import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import { InlineStack, Box, BlockStack, Text } from '@shopify/polaris';
import {
  HomeIcon,
  ProductIcon,
  PriceListIcon,
  ChartLineIcon,
  SettingsIcon,
} from '@shopify/polaris-icons';
import { ShopVerbindungBanner } from '@/components/ShopVerbindungBanner';

/** Shop/Host aus URL oder localStorage – für Link-Preserve */
function useShopParams(): {
  shop: string;
  host: string;
  shopId: string;
  idToken: string;
} {
  const searchParams = useSearchParams();
  const shop =
    searchParams.get('shop') ??
    (typeof window !== 'undefined' ? localStorage.getItem('shop_domain') : null) ??
    '';
  const host =
    searchParams.get('host') ??
    (typeof window !== 'undefined' ? localStorage.getItem('shopify_host') : null) ??
    '';
  const shopId =
    searchParams.get('shop_id') ??
    (typeof window !== 'undefined' ? localStorage.getItem('current_shop_id') : null) ??
    '';
  const idToken = searchParams.get('id_token') ?? '';
  return { shop, host, shopId, idToken };
}

const NAV_ITEMS = [
  { label: 'Übersicht', url: '/dashboard', icon: HomeIcon },
  { label: 'Produkte', url: '/dashboard/products', icon: ProductIcon },
  { label: 'Preisempfehlungen', url: '/dashboard/pricing', icon: PriceListIcon },
  { label: 'Analysen', url: '/dashboard/analytics', icon: ChartLineIcon },
  { label: 'Einstellungen', url: '/dashboard/settings', icon: SettingsIcon },
] as const;

export function DashboardNav({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
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

  const linkSuffix = useMemo(() => {
    const p = new URLSearchParams();
    if (shop) p.set('shop', shop);
    if (host) p.set('host', host);
    if (shopId) p.set('shop_id', shopId);
    if (idToken) p.set('id_token', idToken);
    const q = p.toString();
    return q ? `?${q}` : '';
  }, [shop, host, shopId, idToken]);

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Dunkle Sidebar */}
      <aside
        style={{
          width: 240,
          minWidth: 240,
          background: '#1e1b4b',
          padding: '16px 12px',
          flexShrink: 0,
        }}
      >
        <Box paddingBlock="400" paddingInline="300">
          <InlineStack gap="200" blockAlign="center">
            <div
              style={{
                width: 32,
                height: 32,
                background: 'linear-gradient(135deg, #4F46E5, #7C3AED)',
                borderRadius: 8,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <span style={{ color: 'white', fontSize: 14, fontWeight: 700 }}>
                v
              </span>
            </div>
            <Text variant="headingMd" as="span" fontWeight="bold">
              vlerafy
            </Text>
          </InlineStack>
        </Box>

        <BlockStack gap="100">
          {NAV_ITEMS.map((item) => {
            const href = item.url + linkSuffix;
            const isSelected =
              pathname === item.url ||
              (item.url !== '/dashboard' && pathname.startsWith(item.url));
            const IconComponent = item.icon;
            return (
              <Link key={item.url} href={href} style={{ textDecoration: 'none' }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    padding: '10px 12px',
                    borderRadius: 8,
                    background: isSelected
                      ? 'rgba(99, 102, 241, 0.25)'
                      : 'transparent',
                    color: isSelected ? '#ffffff' : '#c7d2fe',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = 'rgba(255,255,255,0.08)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = 'transparent';
                    }
                  }}
                >
                  <span style={{ display: 'flex', color: 'inherit' }}>
                    <IconComponent />
                  </span>
                  <Text as="span" variant="bodyMd" fontWeight={isSelected ? 'semibold' : 'regular'}>
                    {item.label}
                  </Text>
                </div>
              </Link>
            );
          })}
        </BlockStack>
      </aside>

      {/* Hauptbereich */}
      <main style={{ flex: 1, background: '#f8f9fb', padding: 24 }}>
        <BlockStack gap="400">
          <ShopVerbindungBanner />
          <Box paddingBlockStart="200">{children}</Box>
        </BlockStack>
      </main>
    </div>
  );
}
