'use client';

import { useEffect, useMemo } from 'react';
import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { LayoutDashboard, Package, Tag, Settings } from 'lucide-react';
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
  { href: '/dashboard', label: 'Übersicht', icon: LayoutDashboard },
  { href: '/dashboard/products', label: 'Produkte', icon: Package },
  { href: '/dashboard/pricing', label: 'Preisempfehlungen', icon: Tag, badgeKey: true },
  { href: '/dashboard/settings', label: 'Einstellungen', icon: Settings },
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
      <nav className="vlerafy-sidebar">
        <div className="vlerafy-sidebar-logo">
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: 8,
              background: 'linear-gradient(135deg, var(--v-navy-800), var(--v-navy-700))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 13,
              fontWeight: 800,
              color: 'var(--v-white)',
              flexShrink: 0,
            }}
          >
            {shopName?.charAt(0)?.toUpperCase() || 'V'}
          </div>
          <div className="vlerafy-sidebar-logo-text">
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--v-gray-100)', lineHeight: 1.2 }}>
              {shopName || 'Vlerafy'}
            </div>
            <div style={{ fontSize: 10, color: 'var(--v-gray-600)', fontWeight: 500 }}>
              Pricing Intelligence
            </div>
          </div>
        </div>
        <s-stack direction="block" gap="0">
          {NAV_ITEMS.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href !== '/dashboard' && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href + linkSuffix}
                className={`vlerafy-nav-item ${isActive ? 'vlerafy-nav-item--active' : ''}`}
              >
                <item.icon size={16} strokeWidth={1.8} style={{ flexShrink: 0, opacity: isActive ? 1 : 0.6 }} />
                <span>{item.label}</span>
                {'badgeKey' in item && item.badgeKey && openCount > 0 && (
                  <span className="vlerafy-nav-badge">{openCount}</span>
                )}
              </Link>
            );
          })}
        </s-stack>
        <div style={{ padding: '12px 20px', borderTop: '1px solid rgba(255,255,255,0.08)', marginTop: 'auto' }}>
          <div style={{ fontSize: 10, color: 'var(--v-gray-700)', fontWeight: 500, letterSpacing: '0.05em' }}>
            VLERAFY · BETA
          </div>
        </div>
      </nav>
      <main className="vlerafy-main">
        <s-stack direction="block" gap="4">
          <ShopVerbindungBanner />
          <s-box padding="2">{children}</s-box>
        </s-stack>
      </main>
    </div>
  );
}
