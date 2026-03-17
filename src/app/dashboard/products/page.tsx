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

type FilterTab = 'all' | 'recommended' | 'no-stock';

function useShopSuffix(): string {
  const searchParams = useSearchParams();
  const shop    = searchParams.get('shop')     ?? (typeof window !== 'undefined' ? localStorage.getItem('shop_domain')      : null) ?? '';
  const host    = searchParams.get('host')     ?? (typeof window !== 'undefined' ? localStorage.getItem('shopify_host')     : null) ?? '';
  const shopId  = searchParams.get('shop_id') ?? (typeof window !== 'undefined' ? localStorage.getItem('current_shop_id')  : null) ?? '';
  const idToken = searchParams.get('id_token') ?? '';
  const p = new URLSearchParams();
  if (shop)    p.set('shop',     shop);
  if (host)    p.set('host',     host);
  if (shopId)  p.set('shop_id',  shopId);
  if (idToken) p.set('id_token', idToken);
  return p.toString() ? `?${p.toString()}` : '';
}

function ArrowRightIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      <path d="M4.5 2.5l4 4-4 4" />
    </svg>
  );
}

export default function ProductsPage() {
  const router       = useRouter();
  const queryClient  = useQueryClient();
  const suffix       = useShopSuffix();
  const autoSyncDone = useRef(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab,   setActiveTab  ] = useState<FilterTab>('all');

  const { data: products = [], isLoading } = useQuery({
    queryKey: ['products'],
    queryFn:  () => fetchProducts(),
  });
  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn:  getDashboardStats,
  });
  const { data: recsData } = useQuery({
    queryKey: ['recommendations-list'],
    queryFn:  () => getRecommendationsList('all'),
  });
  const syncMutation = useMutation({
    mutationFn: syncProductsFromShopify,
    onSuccess:  () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      queryClient.invalidateQueries({ queryKey: ['recommendations-list'] });
    },
  });

  const productIdsWithRec = new Set(
    (recsData?.recommendations ?? []).map((r) => r.product_id)
  );

  /* ── Derived counts (für Tabs) ── */
  const totalProducts      = products.length || (stats?.products_count ?? 0);
  const withRecommendation = productIdsWithRec.size || (stats?.products_with_recommendations ?? 0);
  const noStock            = (products ?? []).filter((p) => (p.inventory ?? 0) === 0).length;

  /* ── Filter: zuerst Tab, dann Suche ── */
  const tabFiltered = (products ?? []).filter((p) => {
    if (activeTab === 'recommended') return productIdsWithRec.has(p.id);
    if (activeTab === 'no-stock')    return (p.inventory ?? 0) === 0;
    return true;
  });
  const filteredProducts = tabFiltered.filter((p) =>
    p.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

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

  const handleSync       = () => syncMutation.mutate();
  const handleAnalyzeAll = () => router.push(`/dashboard/pricing${suffix}`);
  const backAction       = JSON.stringify({ content: 'Übersicht', url: '/dashboard' + suffix });

  /* ── Loading ── */
  if (isLoading) {
    return (
      <s-page title="Produkte" back-action={backAction}>
        <div className="piq-dashboard">
          <div className="piq-card">
            <div className="piq-loading"><s-spinner size="small" /></div>
          </div>
        </div>
      </s-page>
    );
  }

  /* ── Empty State (keine Produkte im Shop) ── */
  if (products.length === 0 && !syncMutation.isPending) {
    return (
      <s-page title="Produkte" back-action={backAction}>
        <s-banner tone="info" title="Noch keine Produkte geladen">
          <s-stack direction="block" gap="3">
            <s-paragraph>Verbinde deinen Shopify-Shop um smarte Preisempfehlungen zu erhalten.</s-paragraph>
            <s-button variant="primary" onClick={handleSync} disabled={syncMutation.isPending}>
              Produkte synchronisieren
            </s-button>
          </s-stack>
        </s-banner>
      </s-page>
    );
  }

  return (
    <s-page title="Produkte" back-action={backAction}>
      <div className="piq-dashboard">

        {/* ── Status-Banner ── */}
        {syncMutation.isPending && (
          <s-banner tone="info">
            <s-paragraph>Produkte werden von deinem Shopify-Shop synchronisiert…</s-paragraph>
          </s-banner>
        )}
        {syncMutation.isError && (
          <s-banner tone="critical" title="Synchronisation fehlgeschlagen">
            <s-stack direction="block" gap="2">
              <s-paragraph>Bitte erneut versuchen.</s-paragraph>
              <s-button variant="primary" size="slim" onClick={() => syncMutation.mutate()}>
                Erneut versuchen
              </s-button>
            </s-stack>
          </s-banner>
        )}

        {/* ══ TABELLE mit integrierter Tab-Navigation + Actions ══ */}
        <div className="piq-table-card">

          {/* ── Tab-Bar: Tabs links, Actions rechts ── */}
          <div className="piq-tab-bar">
            <div className="piq-tabs" role="tablist">
              <button
                role="tab"
                aria-selected={activeTab === 'all'}
                className={`piq-tab${activeTab === 'all' ? ' piq-tab--active' : ''}`}
                onClick={() => setActiveTab('all')}
              >
                Alle
                <span className="piq-tab-badge">{totalProducts}</span>
              </button>
              <button
                role="tab"
                aria-selected={activeTab === 'recommended'}
                className={`piq-tab${activeTab === 'recommended' ? ' piq-tab--active' : ''}`}
                onClick={() => setActiveTab('recommended')}
              >
                Mit Empfehlung
                <span className="piq-tab-badge piq-tab-badge--amber">{withRecommendation}</span>
              </button>
              <button
                role="tab"
                aria-selected={activeTab === 'no-stock'}
                className={`piq-tab${activeTab === 'no-stock' ? ' piq-tab--active' : ''}`}
                onClick={() => setActiveTab('no-stock')}
              >
                Kein Lagerbestand
                <span className="piq-tab-badge piq-tab-badge--red">{noStock}</span>
              </button>
            </div>
            <div className="piq-tab-actions">
              <s-button
                variant="secondary"
                size="slim"
                onClick={handleSync}
                disabled={syncMutation.isPending}
                loading={syncMutation.isPending}
              >
                Synchronisieren
              </s-button>
              <s-button variant="primary" size="slim" onClick={handleAnalyzeAll}>
                Alle Empfehlungen
              </s-button>
            </div>
          </div>

          {/* ── Suchfeld + Anzahl ── */}
          <div className="piq-table-toolbar">
            <div className="piq-table-search">
              <span className="piq-table-search-icon" aria-hidden="true">
                <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
                  <circle cx="6.5" cy="6.5" r="5" />
                  <path d="m10.5 10.5 3 3" />
                </svg>
              </span>
              <s-text-field
                label=""
                placeholder="Produkt suchen…"
                value={searchQuery}
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                onChange={(e: any) => setSearchQuery(e?.target?.value ?? e?.detail?.value ?? '')}
              />
            </div>
            <span className="piq-table-count">{filteredProducts.length} Produkte</span>
          </div>

          {/* ── Tabelle ── */}
          <div style={{ overflowX: 'auto' }}>
            <table className="piq-table">
              <thead>
                <tr>
                  <th>Produkt</th>
                  <th style={{ textAlign: 'right' }}>Preis</th>
                  <th style={{ textAlign: 'center' }}>Lagerbestand</th>
                  <th style={{ textAlign: 'center' }}>Empfehlung</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.length === 0 ? (
                  <tr>
                    <td colSpan={5}>
                      <div className="piq-table-empty">
                        <div className="piq-table-empty-icon">
                          {activeTab === 'no-stock' ? '📦' : '🔍'}
                        </div>
                        <s-paragraph>
                          {activeTab === 'recommended'
                            ? 'Keine Produkte mit ausstehenden Empfehlungen.'
                            : activeTab === 'no-stock'
                            ? 'Alle Produkte haben Lagerbestand.'
                            : searchQuery
                            ? `Keine Ergebnisse für „${searchQuery}"`
                            : 'Keine Produkte gefunden.'}
                        </s-paragraph>
                        {activeTab === 'all' && searchQuery && (
                          <s-paragraph tone="subdued">Versuche einen anderen Suchbegriff.</s-paragraph>
                        )}
                        {activeTab === 'all' && !searchQuery && (
                          <div style={{ marginTop: 12 }}>
                            <s-button variant="primary" size="slim" onClick={handleSync}>
                              Jetzt synchronisieren
                            </s-button>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredProducts.map((product) => (
                    <tr
                      key={product.id}
                      tabIndex={0}
                      onClick={() => router.push(`/dashboard/products/${product.id}${suffix}`)}
                      onKeyDown={(e) => e.key === 'Enter' && router.push(`/dashboard/products/${product.id}${suffix}`)}
                    >
                      {/* Produkt-Name + Avatar */}
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <div className="piq-product-avatar">
                            {product.image
                              ? <img src={product.image} alt={product.title} />
                              : <span>{product.title.charAt(0)}</span>
                            }
                          </div>
                          <span className="piq-product-name">{product.title}</span>
                        </div>
                      </td>

                      {/* Preis */}
                      <td className="piq-table-price" style={{ textAlign: 'right' }}>
                        {product.price != null
                          ? `${product.price.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`
                          : '—'}
                      </td>

                      {/* Lagerbestand — nur 0 = roter Badge, sonst plain text */}
                      <td style={{ textAlign: 'center' }}>
                        {(product.inventory ?? 0) === 0
                          ? <s-badge tone="critical">0 Stück</s-badge>
                          : <span className="piq-stock-text">{product.inventory} Stück</span>
                        }
                      </td>

                      {/* Empfehlung — warning für ausstehend, neutral für keine Daten */}
                      <td style={{ textAlign: 'center' }}>
                        {productIdsWithRec.has(product.id)
                          ? <s-badge tone="warning">Ausstehend</s-badge>
                          : <span className="piq-table-muted">—</span>
                        }
                      </td>

                      {/* Action — nur bei ausstehender Empfehlung */}
                      <td style={{ textAlign: 'right' }}>
                        <span className="piq-table-action-btn">
                          Ansehen <ArrowRightIcon />
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

        </div>
      </div>
    </s-page>
  );
}
