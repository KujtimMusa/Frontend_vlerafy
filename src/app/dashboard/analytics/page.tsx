'use client';

import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import {
  getDashboardStats,
  getEngineStatus,
  fetchProducts,
  getMarginHistory,
} from '@/lib/api';
import { StatKarte } from '@/components/StatKarte';
import { FortschrittsCard } from '@/components/FortschrittsCard';
import { PreisverlaufChart } from '@/components/PreisverlaufChart';

function useShopSuffix(): string {
  const searchParams = useSearchParams();
  const shop = searchParams.get('shop') ?? (typeof window !== 'undefined' ? localStorage.getItem('shop_domain') : null) ?? '';
  const host = searchParams.get('host') ?? (typeof window !== 'undefined' ? localStorage.getItem('shopify_host') : null) ?? '';
  const shopId = searchParams.get('shop_id') ?? (typeof window !== 'undefined' ? localStorage.getItem('current_shop_id') : null) ?? '';
  const idToken = searchParams.get('id_token') ?? '';
  const p = new URLSearchParams();
  if (shop) p.set('shop', shop);
  if (host) p.set('host', host);
  if (shopId) p.set('shop_id', shopId);
  if (idToken) p.set('id_token', idToken);
  return p.toString() ? `?${p.toString()}` : '';
}

export default function AnalyticsPage() {
  const router = useRouter();
  const suffix = useShopSuffix();
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });
  const { data: engineStatus } = useQuery({
    queryKey: ['engine-status'],
    queryFn: getEngineStatus,
  });
  const { data: products = [] } = useQuery({
    queryKey: ['products'],
    queryFn: () => fetchProducts(),
  });
  const topProduct = products[0];
  const { data: historyData } = useQuery({
    queryKey: ['margin-history', topProduct?.shopify_product_id],
    queryFn: () =>
      getMarginHistory(topProduct!.shopify_product_id, 30),
    enabled: !!topProduct?.shopify_product_id,
  });

  const chartData =
    historyData?.history?.map((h) => ({
      date: new Date(h.date).toLocaleDateString('de-DE', {
        day: '2-digit',
        month: '2-digit',
      }),
      price: h.selling_price,
    })) ?? [];

  if (isLoading) {
    return (
      <div className="vlerafy-main">
        <div className="vlerafy-page-header">
          <div className="vlerafy-skeleton vlerafy-skeleton-title" />
          <div
            className="vlerafy-skeleton vlerafy-skeleton-text"
            style={{ width: '60%' }}
          />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="vlerafy-skeleton vlerafy-skeleton-card" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="vlerafy-main">
      <div className="vlerafy-page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <h1 className="vlerafy-page-title">Analysen</h1>
        <s-button
          variant="primary"
          onClick={() => router.push(`/dashboard/pricing${suffix}`)}
        >
          Produkte optimieren
        </s-button>
      </div>
      <s-stack direction="block" gap="5">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
          <StatKarte
            value={stats?.recommendations_pending ?? 0}
            label="Ausstehend"
            icon={<span style={{ fontSize: 18 }}>⚠️</span>}
            tone="warning"
          />
          <StatKarte
            value={stats?.recommendations_applied ?? 0}
            label="Umgesetzt"
            icon={<span style={{ fontSize: 18 }}>✓</span>}
            tone="success"
          />
          <StatKarte
            value={stats?.products_with_recommendations ?? 0}
            label="Analysiert"
            icon={<span style={{ fontSize: 18 }}>📊</span>}
            tone="neutral"
          />
          <StatKarte
            value={`€${stats?.missed_revenue?.total?.toFixed(0) ?? '0'}`}
            label="Potenzial"
            icon={<span style={{ fontSize: 18 }}>📈</span>}
            tone="critical"
          />
        </div>

        <PreisverlaufChart
          data={chartData}
          title="Preisentwicklung"
          subtitle="Letzte 30 Tage (erstes Produkt)"
        />

        {engineStatus && (
          <s-section>
            <s-stack direction="block" gap="4">
              <s-heading size="md">Preisanalyse-Engine</s-heading>
              <s-stack direction="inline" gap="2" style={{ alignItems: 'center' }}>
                <s-badge tone={engineStatus.feature_flags ? 'success' : 'warning'}>
                  {engineStatus.feature_flags ? 'Aktiv' : 'Prüfen'}
                </s-badge>
                <s-paragraph tone="subdued">Datenbasierte Preisanalyse v1.2</s-paragraph>
              </s-stack>
            </s-stack>
          </s-section>
        )}

        {stats?.progress && (
          <FortschrittsCard progress={stats.progress} />
        )}
      </s-stack>
    </div>
  );
}
