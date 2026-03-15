'use client';

import { useEffect, useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  fetchProducts,
  getDashboardStats,
  getRecommendationsList,
  syncProductsFromShopify,
} from '@/lib/api';

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

export default function ProductsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const suffix = useShopSuffix();
  const autoSyncDone = useRef(false);
  const [searchQuery, setSearchQuery] = useState('');

  const { data: products = [], isLoading } = useQuery({
    queryKey: ['products'],
    queryFn: () => fetchProducts(),
  });
  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });
  const { data: recsData } = useQuery({
    queryKey: ['recommendations-list'],
    queryFn: () => getRecommendationsList('all'),
  });
  const syncMutation = useMutation({
    mutationFn: syncProductsFromShopify,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      queryClient.invalidateQueries({ queryKey: ['recommendations-list'] });
    },
  });

  const productIdsWithRec = new Set((recsData?.recommendations ?? []).map((r) => r.product_id));
  const filteredProducts = (products ?? []).filter((p) =>
    p.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const totalProducts = stats?.products_count ?? products.length;
  const withRecommendation = stats?.products_with_recommendations ?? 0;
  const outOfStock = (products ?? []).filter((p) => (p.inventory ?? 0) === 0).length;
  const potentialRevenue = stats?.missed_revenue?.total ?? 0;
  const displayPotential = Math.abs(potentialRevenue);

  useEffect(() => {
    if (
      !isLoading &&
      products.length === 0 &&
      !autoSyncDone.current &&
      typeof window !== 'undefined' &&
      (localStorage.getItem('shop_domain') || localStorage.getItem('current_shop_id'))
    ) {
      autoSyncDone.current = true;
      syncMutation.mutate();
    }
  }, [isLoading, products.length, syncMutation]);

  const handleSync = () => syncMutation.mutate();
  const handleAnalyzeAll = () => router.push(`/dashboard/pricing${suffix}`);

  if (isLoading) {
    return (
      <div className="vlerafy-main">
        <div className="vlerafy-skeleton vlerafy-skeleton-title" style={{ marginBottom: 20 }} />
        <div className="vlerafy-skeleton vlerafy-skeleton-card" />
      </div>
    );
  }

  if (products.length === 0 && !syncMutation.isPending) {
    return (
      <div className="vlerafy-main">
        <div className="vlerafy-empty-state">
          <div className="vlerafy-empty-state-icon">📦</div>
          <p className="vlerafy-empty-state-title">Noch keine Produkte geladen</p>
          <p className="vlerafy-empty-state-text">
            Verbinde deinen Shopify-Shop um smarte Preisempfehlungen zu erhalten.
          </p>
          <s-button
            variant="primary"
            onClick={handleSync}
            disabled={syncMutation.isPending}
          >
            Produkte synchronisieren
          </s-button>
        </div>
      </div>
    );
  }

  const statsData = [
    {
      label: 'Produkte gesamt',
      value: String(totalProducts),
      valueColor: 'var(--v-gray-950)',
      icon: '◫',
      sub: null as string | null,
    },
    {
      label: 'Mit Empfehlung',
      value: String(withRecommendation),
      valueColor: 'var(--v-navy-800)',
      icon: '◈',
      sub: totalProducts > 0 ? `${Math.round((withRecommendation / totalProducts) * 100)}% aller Produkte` : null,
    },
    {
      label: 'Kein Lagerbestand',
      value: String(outOfStock),
      valueColor: outOfStock > 0 ? 'var(--v-critical)' : 'var(--v-success)',
      icon: '◎',
      sub: outOfStock > 0 ? 'Produkte prüfen' : 'Alles vorrätig',
    },
    {
      label: 'Möglicher Mehrumsatz',
      value: '+€' + displayPotential.toLocaleString('de-DE', { maximumFractionDigits: 0 }),
      valueColor: 'var(--v-success)',
      icon: '◉',
      sub: 'bei Umsetzung aller Empfehlungen',
    },
  ];

  return (
    <div className="vlerafy-main">
      {syncMutation.isPending && (
        <div
          style={{
            background: 'var(--v-info-bg)',
            border: '1px solid var(--v-navy-100)',
            borderRadius: 'var(--v-radius-sm)',
            padding: '12px 18px',
            marginBottom: 20,
            fontSize: 14,
            color: 'var(--v-navy-700)',
          }}
        >
          Produkte werden von deinem Shopify-Shop synchronisiert...
        </div>
      )}
      {syncMutation.isError && (
        <div
          style={{
            background: 'var(--v-critical-bg)',
            border: '1px solid var(--v-critical-muted)',
            borderRadius: 'var(--v-radius-sm)',
            padding: '12px 18px',
            marginBottom: 20,
            fontSize: 14,
            color: 'var(--v-critical)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <span>Sync fehlgeschlagen. Bitte erneut versuchen.</span>
          <s-button
            variant="destructive"
            size="slim"
            onClick={() => syncMutation.mutate()}
          >
            Erneut versuchen
          </s-button>
        </div>
      )}

      <div className="vlerafy-page-header">
        <s-stack direction="inline" align-items="center" justify-content="space-between" style={{ flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 className="vlerafy-page-title">Produkte</h1>
            <p className="vlerafy-page-subtitle">
              {totalProducts} Produkte · {withRecommendation} mit Empfehlung
            </p>
          </div>
          <s-stack direction="inline" gap="2">
            <s-button variant="secondary" onClick={handleAnalyzeAll}>
              Alle analysieren
            </s-button>
            <s-button
              variant="primary"
              onClick={handleSync}
              disabled={syncMutation.isPending}
              loading={syncMutation.isPending}
            >
              Synchronisieren
            </s-button>
          </s-stack>
        </s-stack>
      </div>

      <s-grid columns="4" gap="4" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(195px, 1fr))', gap: 12, marginBottom: 20 }}>
        {statsData.map((stat) => (
          <div key={stat.label} className="vlerafy-stat-card">
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                marginBottom: 8,
              }}
            >
              <span
                style={{
                  fontSize: 11,
                  color: 'var(--v-gray-400)',
                  fontWeight: 500,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                }}
              >
                {stat.label}
              </span>
              <span style={{ fontSize: 16, color: 'var(--v-gray-300)' }}>{stat.icon}</span>
            </div>
            <p className="vlerafy-stat-value" style={{ color: stat.valueColor, marginBottom: stat.sub ? 6 : 0 }}>
              {stat.value}
            </p>
            {stat.sub && (
              <span style={{ fontSize: 11, color: 'var(--v-gray-400)' }}>{stat.sub}</span>
            )}
          </div>
        ))}
      </s-grid>

      <s-section>
        <s-stack direction="block" gap="0">
          <div
            style={{
              padding: '12px 18px',
              borderBottom: '1px solid var(--v-gray-100)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
            }}
          >
            <div style={{ position: 'relative' }}>
              <span
                style={{
                  position: 'absolute',
                  left: 9,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--v-gray-400)',
                  fontSize: 13,
                  pointerEvents: 'none',
                }}
              >
                🔍
              </span>
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Produkt suchen..."
                style={{
                  paddingLeft: 28,
                  paddingRight: 12,
                  paddingTop: 6,
                  paddingBottom: 6,
                  border: '1px solid var(--v-gray-200)',
                  borderRadius: 'var(--v-radius-sm)',
                  fontSize: 13,
                  outline: 'none',
                  background: 'var(--v-gray-50)',
                  color: 'var(--v-gray-950)',
                  width: 220,
                }}
              />
            </div>
            <span style={{ fontSize: 12, color: 'var(--v-gray-400)' }}>
              {filteredProducts.length} Produkte
            </span>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 120px 100px 130px 90px',
              padding: '9px 18px',
              background: 'var(--v-gray-50)',
              borderBottom: '1px solid var(--v-gray-100)',
            }}
          >
            {['Produkt', 'Preis', 'Lager', 'Empfehlung', ''].map((col) => (
              <span
                key={col}
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: 'var(--v-gray-400)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                }}
              >
                {col}
              </span>
            ))}
          </div>

          {filteredProducts.map((product, i) => (
            <div
              key={product.id}
              onClick={() => router.push(`/dashboard/products/${product.id}${suffix}`)}
              className="vlerafy-table-row"
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 120px 100px 130px 90px',
                padding: '12px 18px',
                borderBottom: i < filteredProducts.length - 1 ? '1px solid var(--v-gray-100)' : 'none',
                alignItems: 'center',
                cursor: 'pointer',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 'var(--v-radius-sm)',
                    background: 'var(--v-gray-100)',
                    flexShrink: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 14,
                  }}
                >
                  📦
                </div>
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: 500,
                    color: 'var(--v-gray-950)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {product.title}
                </span>
              </div>

              <span style={{ fontSize: 13, color: 'var(--v-gray-950)', fontWeight: 500 }}>
                {product.price?.toLocaleString('de-DE', { style: 'currency', currency: 'EUR' })}
              </span>

              <span
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color:
                    (product.inventory ?? 0) === 0
                      ? 'var(--v-critical)'
                      : (product.inventory ?? 0) < 10
                        ? 'var(--v-warning)'
                        : 'var(--v-gray-500)',
                }}
              >
                {(product.inventory ?? 0) === 0
                  ? '⚠ 0 Stück'
                  : `${product.inventory ?? 0} Stück`}
              </span>

              <div>
                {productIdsWithRec.has(product.id) ? (
                  <s-badge tone="info">Vorhanden</s-badge>
                ) : (
                  <span style={{ color: 'var(--v-gray-300)', fontSize: 13 }}>—</span>
                )}
              </div>

              <s-button
                variant="plain"
                size="slim"
                onClick={(e: React.MouseEvent) => {
                  e.stopPropagation();
                  router.push(`/dashboard/products/${product.id}${suffix}`);
                }}
              >
                Ansehen →
              </s-button>
            </div>
          ))}

          {filteredProducts.length === 0 && (
            <div className="vlerafy-empty-state" style={{ padding: 40 }}>
              <div className="vlerafy-empty-state-icon" style={{ fontSize: 32 }}>🔍</div>
              <p className="vlerafy-empty-state-title">Keine Produkte gefunden</p>
              <p className="vlerafy-empty-state-text">
                Keine Produkte für „{searchQuery}“
              </p>
            </div>
          )}
        </s-stack>
      </s-section>
    </div>
  );
}
