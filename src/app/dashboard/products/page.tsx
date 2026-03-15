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
  const withRecommendation = stats?.products_with_recommendations ?? productIdsWithRec.size;
  const noStock = (products ?? []).filter((p) => (p.inventory ?? 0) === 0).length;
  const potentialRevenue = stats?.missed_revenue?.total ?? 0;
  const revenue = `+€${Math.abs(potentialRevenue).toLocaleString('de-DE', { maximumFractionDigits: 0 })}`;

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
        <div className="vlerafy-skeleton vlerafy-skeleton-title" />
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

  return (
    <div className="vlerafy-main">
      {syncMutation.isPending && (
        <div className="vlerafy-banner-pending">
          Produkte werden von deinem Shopify-Shop synchronisiert...
        </div>
      )}
      {syncMutation.isError && (
        <div className="vlerafy-banner-error">
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

      <div className="vlerafy-page-header vlerafy-page-header--spaced">
        <s-stack direction="inline" align-items="center" justify-content="space-between">
          <div>
            <h1 className="vlerafy-page-title">Produkte</h1>
            <p className="vlerafy-page-subtitle">
              {totalProducts} Produkte · {withRecommendation} mit Empfehlung
            </p>
          </div>
          <s-stack direction="inline" gap="2">
            <s-button variant="secondary" size="slim" onClick={handleAnalyzeAll}>
              Alle analysieren
            </s-button>
            <s-button
              variant="primary"
              size="slim"
              onClick={handleSync}
              disabled={syncMutation.isPending}
              loading={syncMutation.isPending}
            >
              Synchronisieren
            </s-button>
          </s-stack>
        </s-stack>
      </div>

      <s-grid columns="4" gap="4" className="vlerafy-products-kpi-grid">
        <div className="vlerafy-kpi-card">
          <div className="vlerafy-kpi-card--accent-neutral" />
          <div className="vlerafy-kpi-body">
            <p className="vlerafy-kpi-label">Produkte gesamt</p>
            <p className="vlerafy-kpi-value">{totalProducts}</p>
          </div>
        </div>

        <div className="vlerafy-kpi-card">
          <div className="vlerafy-kpi-card--accent-warning" />
          <div className="vlerafy-kpi-body">
            <p className="vlerafy-kpi-label">Mit Empfehlung</p>
            <p className="vlerafy-kpi-value">{withRecommendation}</p>
            <p className="vlerafy-kpi-sub">
              {totalProducts > 0 ? `${Math.round((withRecommendation / totalProducts) * 100)}% aller Produkte` : '—'}
            </p>
          </div>
        </div>

        <div className="vlerafy-kpi-card">
          <div className="vlerafy-kpi-card--accent-critical" />
          <div className="vlerafy-kpi-body">
            <p className="vlerafy-kpi-label">Kein Lagerbestand</p>
            <p className="vlerafy-kpi-value vlerafy-kpi-value--critical">{noStock}</p>
            <p className="vlerafy-kpi-sub">Produkte prüfen</p>
          </div>
        </div>

        <div className="vlerafy-kpi-card">
          <div className="vlerafy-kpi-card--accent-success" />
          <div className="vlerafy-kpi-body">
            <p className="vlerafy-kpi-label">Möglicher Mehrumsatz</p>
            <p className="vlerafy-kpi-value vlerafy-kpi-value--success">{revenue}</p>
            <p className="vlerafy-kpi-sub">bei Umsetzung aller Empfehlungen</p>
          </div>
        </div>
      </s-grid>

      <div className="vlerafy-table-card">
        <div className="vlerafy-table-toolbar">
          <div className="vlerafy-search-wrapper">
            <svg
              className="vlerafy-search-icon"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
            <input
              className="vlerafy-search-input"
              placeholder="Produkt suchen..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <span className="vlerafy-table-count">{filteredProducts.length} Produkte</span>
        </div>

        <div className="vlerafy-table-wrapper">
          <table className="vlerafy-table">
            <thead>
              <tr>
                <th>Produkt</th>
                <th>Preis</th>
                <th>Lager</th>
                <th>Empfehlung</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filteredProducts.length === 0 ? (
                <tr>
                  <td colSpan={5} className="vlerafy-empty-state vlerafy-empty-state--compact">
                    <div className="vlerafy-empty-state-icon" style={{ fontSize: 32 }}>🔍</div>
                    <p className="vlerafy-empty-state-title">Keine Produkte gefunden</p>
                    <p className="vlerafy-empty-state-text">
                      Keine Produkte für „{searchQuery}“
                    </p>
                  </td>
                </tr>
              ) : (
                filteredProducts.map((product) => (
                  <tr
                    key={product.id}
                    onClick={() => router.push(`/dashboard/products/${product.id}${suffix}`)}
                  >
                    <td>
                      <s-stack direction="inline" align-items="center" gap="3">
                        <div className="vlerafy-product-avatar">
                          {product.image ? (
                            <img src={product.image} alt={product.title} />
                          ) : (
                            <span>{product.title.charAt(0)}</span>
                          )}
                        </div>
                        <span className="vlerafy-product-title">{product.title}</span>
                      </s-stack>
                    </td>
                    <td className="vlerafy-table-price">
                      {product.price != null
                        ? `${product.price.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`
                        : '—'}
                    </td>
                    <td>
                      {(product.inventory ?? 0) === 0 ? (
                        <span className="vlerafy-stock-badge vlerafy-stock-badge--empty">
                          0 Stück
                        </span>
                      ) : (
                        <span className="vlerafy-stock-badge vlerafy-stock-badge--ok">
                          {product.inventory} Stück
                        </span>
                      )}
                    </td>
                    <td>
                      {productIdsWithRec.has(product.id) ? (
                        <s-badge tone="warning">Ausstehend</s-badge>
                      ) : (
                        <span className="vlerafy-table-muted">—</span>
                      )}
                    </td>
                    <td>
                      <span className="vlerafy-table-action">Ansehen →</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
