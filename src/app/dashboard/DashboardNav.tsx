'use client';

import { useEffect, useMemo } from 'react';
import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Box, BlockStack } from '@shopify/polaris';
import { getCurrentShop, getDashboardStats } from '@/lib/api';
import { ShopVerbindungBanner } from '@/components/ShopVerbindungBanner';

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
  { href: '/dashboard', label: 'Übersicht', icon: '▤' },
  { href: '/dashboard/products', label: 'Produkte', icon: '◫' },
  { href: '/dashboard/pricing', label: 'Preisempfehlungen', icon: '◈' },
  { href: '/dashboard/analytics', label: 'Analysen', icon: '◉' },
  { href: '/dashboard/settings', label: 'Einstellungen', icon: '◎' },
] as const;

export function DashboardNav({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { shop, host, shopId, idToken } = useShopParams();

  const { data: shopData } = useQuery({
    queryKey: ['current-shop'],
    queryFn: getCurrentShop,
  });
  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });

  const shopName = shopData?.shop?.name ?? shopData?.shop?.shop_url ?? 'Vlerafy';
  const openCount = stats?.recommendations_pending ?? 0;

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
      {/* Sidebar */}
      <nav
        style={{
          width: 200,
          minHeight: '100vh',
          background: '#0F172A',
          borderRight: '1px solid #1E293B',
          display: 'flex',
          flexDirection: 'column',
          padding: 0,
          position: 'fixed',
          top: 0,
          left: 0,
          bottom: 0,
        }}
      >
        {/* Logo-Bereich */}
        <div
          style={{
            padding: '20px 20px 16px',
            borderBottom: '1px solid #1E293B',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: 8,
              background: 'linear-gradient(135deg, #1E3A5F, #2D5282)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 13,
              fontWeight: 800,
              color: 'white',
              flexShrink: 0,
            }}
          >
            {shopName?.charAt(0)?.toUpperCase() || 'V'}
          </div>
          <div>
            <div
              style={{
                fontSize: 13,
                fontWeight: 700,
                color: '#F1F5F9',
                lineHeight: 1.2,
              }}
            >
              {shopName || 'Vlerafy'}
            </div>
            <div
              style={{
                fontSize: 10,
                color: '#475569',
                fontWeight: 500,
              }}
            >
              Pricing Intelligence
            </div>
          </div>
        </div>

        {/* Navigation */}
        <div style={{ flex: 1, padding: '12px 10px' }}>
          {NAV_ITEMS.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href !== '/dashboard' && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href + linkSuffix}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '8px 12px',
                  borderRadius: 8,
                  marginBottom: 2,
                  background: isActive ? '#1E293B' : 'transparent',
                  color: isActive ? '#F1F5F9' : '#64748B',
                  fontSize: 13,
                  fontWeight: isActive ? 600 : 400,
                  textDecoration: 'none',
                  transition: 'all 0.15s',
                  border: isActive
                    ? '1px solid #334155'
                    : '1px solid transparent',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = '#1E293B';
                    e.currentTarget.style.color = '#CBD5E1';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'transparent';
                    e.currentTarget.style.color = '#64748B';
                  }
                }}
              >
                <span
                  style={{ fontSize: 15, opacity: isActive ? 1 : 0.6 }}
                >
                  {item.icon}
                </span>
                {item.label}
                {item.label === 'Preisempfehlungen' && openCount > 0 && (
                  <span
                    style={{
                      marginLeft: 'auto',
                      background: '#1E3A5F',
                      color: '#93C5FD',
                      borderRadius: 20,
                      padding: '1px 7px',
                      fontSize: 11,
                      fontWeight: 700,
                    }}
                  >
                    {openCount}
                  </span>
                )}
              </Link>
            );
          })}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '12px 20px',
            borderTop: '1px solid #1E293B',
          }}
        >
          <div
            style={{
              fontSize: 10,
              color: '#334155',
              fontWeight: 500,
              letterSpacing: '0.05em',
            }}
          >
            VLERAFY · BETA
          </div>
        </div>
      </nav>

      {/* Hauptbereich – mit margin-left für fixed Sidebar */}
      <main
        style={{
          flex: 1,
          marginLeft: 200,
          background: '#F8FAFC',
          padding: 24,
        }}
      >
        <BlockStack gap="400">
          <ShopVerbindungBanner />
          <Box paddingBlockStart="200">{children}</Box>
        </BlockStack>
      </main>
    </div>
  );
}
