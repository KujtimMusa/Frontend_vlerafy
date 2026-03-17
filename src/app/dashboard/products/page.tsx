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

type FilterTab = 'all' | 'recommended' | 'no-stock' | 'no-cost';

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

function CheckIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2.5 6.5l2.5 2.5 4.5-5" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      <path d="M2 2l6 6M8 2l-6 6" />
    </svg>
  );
}

const strategyLabels: Record<string, string> = {
  demand_pricing: 'Nachfrage',
  demand_inventory_signal: 'Nachfrage-Signal',
  competitive_pricing: 'Wettbewerb',
  margin_optimization: 'Marge',
  inventory_clearance: 'Abverkauf',
  inventory_normal_no_sales: 'Lager-Optimierung',
  premium_pricing: 'Premium',
  psychological_pricing: 'Psycho-Preis',
  ML_OPTIMIZED_CONSTRAINED: 'KI-optimiert',
  ml_optimized: 'KI-optimiert',
};

function readableStrategy(raw: string): string {
  if (strategyLabels[raw]) return strategyLabels[raw];
  return raw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function stockLevel(qty: number): { label: string; tone: string } {
  if (qty === 0) return { label: 'Ausverkauft', tone: 'red' };
  if (qty <= 10) return { label: 'Niedrig', tone: 'amber' };
  return { label: 'Verfügbar', tone: 'green' };
}

function ConfBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="piq-conf-mini">
      <div className="piq-conf-mini-track">
        <div className="piq-conf-mini-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="piq-conf-mini-pct">{pct}%</span>
    </div>
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

  type Rec = NonNullable<typeof recsData>['recommendations'][number];
  const recMap = new Map<number, Rec>();
  (recsData?.recommendations ?? []).forEach((r) => recMap.set(r.product_id, r));

  const totalProducts      = products.length || (stats?.products_count ?? 0);
  const withRecommendation = recMap.size || (stats?.products_with_recommendations ?? 0);
  const noStock            = products.filter((p) => (p.inventory ?? 0) === 0).length;
  const withCost           = products.filter((p) => p.cost != null && p.cost > 0).length;
  const noCost             = totalProducts - withCost;

  const tabFiltered = products.filter((p) => {
    if (activeTab === 'recommended') return recMap.has(p.id);
    if (activeTab === 'no-stock')    return (p.inventory ?? 0) === 0;
    if (activeTab === 'no-cost')     return p.cost == null || p.cost === 0;
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

  const handleSync = () => syncMutation.mutate();
  const backAction = JSON.stringify({ content: 'Übersicht', url: '/dashboard' + suffix });

  if (isLoading) {
    return (
      <s-page title="Produkte" back-action={backAction}>
        <div className="piq-dashboard">
          <div className="piq-card"><div className="piq-loading"><s-spinner size="small" /></div></div>
        </div>
      </s-page>
    );
  }

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

        {syncMutation.isPending && (
          <s-banner tone="info"><s-paragraph>Produkte werden synchronisiert…</s-paragraph></s-banner>
        )}
        {syncMutation.isError && (
          <s-banner tone="critical" title="Synchronisation fehlgeschlagen">
            <s-stack direction="block" gap="2">
              <s-paragraph>Bitte erneut versuchen.</s-paragraph>
              <s-button variant="primary" size="slim" onClick={() => syncMutation.mutate()}>Erneut versuchen</s-button>
            </s-stack>
          </s-banner>
        )}

        {/* ══ TABELLE ══ */}
        <div className="piq-table-card">

          {/* ── Tab-Bar ── */}
          <div className="piq-tab-bar">
            <div className="piq-tabs" role="tablist">
              <button role="tab" aria-selected={activeTab === 'all'}
                className={`piq-tab${activeTab === 'all' ? ' piq-tab--active' : ''}`}
                onClick={() => setActiveTab('all')}>
                Alle <span className="piq-tab-badge">{totalProducts}</span>
              </button>
              <button role="tab" aria-selected={activeTab === 'recommended'}
                className={`piq-tab${activeTab === 'recommended' ? ' piq-tab--active' : ''}`}
                onClick={() => setActiveTab('recommended')}>
                Empfehlung <span className="piq-tab-badge piq-tab-badge--amber">{withRecommendation}</span>
              </button>
              <button role="tab" aria-selected={activeTab === 'no-stock'}
                className={`piq-tab${activeTab === 'no-stock' ? ' piq-tab--active' : ''}`}
                onClick={() => setActiveTab('no-stock')}>
                Ausverkauft <span className="piq-tab-badge piq-tab-badge--red">{noStock}</span>
              </button>
              <button role="tab" aria-selected={activeTab === 'no-cost'}
                className={`piq-tab${activeTab === 'no-cost' ? ' piq-tab--active' : ''}`}
                onClick={() => setActiveTab('no-cost')}>
                Ohne Kosten <span className="piq-tab-badge">{noCost}</span>
              </button>
            </div>
          </div>

          {/* ── Suchfeld + Anzahl ── */}
          <div className="piq-table-toolbar">
            <div className="piq-table-search">
              <span className="piq-table-search-icon" aria-hidden="true">
                <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
                  <circle cx="6.5" cy="6.5" r="5" /><path d="m10.5 10.5 3 3" />
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
            <table className="piq-table piq-table--rich">
              <thead>
                <tr>
                  <th>Produkt</th>
                  <th style={{ textAlign: 'right' }}>Preis</th>
                  <th style={{ textAlign: 'center' }}>Lager</th>
                  <th style={{ textAlign: 'center' }}>Kosten</th>
                  <th style={{ textAlign: 'center' }}>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.length === 0 ? (
                  <tr>
                    <td colSpan={6}>
                      <div className="piq-table-empty">
                        <div className="piq-table-empty-icon">
                          {activeTab === 'no-stock' ? '📦' : activeTab === 'no-cost' ? '💰' : '🔍'}
                        </div>
                        <s-paragraph>
                          {activeTab === 'recommended'
                            ? 'Keine Produkte mit ausstehenden Empfehlungen.'
                            : activeTab === 'no-stock'
                            ? 'Alle Produkte haben Lagerbestand.'
                            : activeTab === 'no-cost'
                            ? 'Alle Produkte haben Kosten hinterlegt.'
                            : searchQuery
                            ? `Keine Ergebnisse f\u00FCr \u201E${searchQuery}\u201C`
                            : 'Keine Produkte gefunden.'}
                        </s-paragraph>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredProducts.map((product) => {
                    const rec = recMap.get(product.id);
                    const hasCost = product.cost != null && product.cost > 0;
                    const stock = stockLevel(product.inventory ?? 0);
                    const isApplied = rec?.applied_at != null;
                    const hasRec = !!rec;
                    const accentClass = isApplied
                      ? 'piq-row--applied'
                      : hasRec
                      ? 'piq-row--pending'
                      : '';

                    return (
                      <tr
                        key={product.id}
                        className={accentClass}
                        tabIndex={0}
                        onClick={() => router.push(`/dashboard/products/${product.id}${suffix}`)}
                        onKeyDown={(e) => e.key === 'Enter' && router.push(`/dashboard/products/${product.id}${suffix}`)}
                      >
                        {/* Produkt */}
                        <td>
                          <div className="piq-prod-cell">
                            <div className={`piq-product-avatar${hasRec ? ' piq-product-avatar--rec' : ''}`}>
                              {product.image
                                ? <img src={product.image} alt={product.title} />
                                : <span>{product.title.charAt(0)}</span>
                              }
                            </div>
                            <div className="piq-prod-info">
                              <span className="piq-product-name">{product.title}</span>
                              {rec ? (
                                <span className="piq-prod-meta">
                                  <span className={`piq-strat-tag piq-strat-tag--${isApplied ? 'green' : 'indigo'}`}>
                                    {readableStrategy(rec.strategy)}
                                  </span>
                                  <ConfBar value={rec.confidence} />
                                </span>
                              ) : (
                                <span className="piq-prod-meta piq-prod-meta--dim">Noch nicht analysiert</span>
                              )}
                            </div>
                          </div>
                        </td>

                        {/* Preis */}
                        <td style={{ textAlign: 'right' }}>
                          <div className="piq-price-cell">
                            <span className="piq-price-current">
                              {product.price != null
                                ? `${product.price.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`
                                : '—'}
                            </span>
                            {rec && rec.recommended_price !== rec.current_price && (
                              <span className={`piq-price-rec${rec.recommended_price > rec.current_price ? '' : ' piq-price-rec--down'}`}>
                                → {rec.recommended_price.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €
                              </span>
                            )}
                          </div>
                        </td>

                        {/* Lagerbestand */}
                        <td style={{ textAlign: 'center' }}>
                          <div className={`piq-stock-pill piq-stock-pill--${stock.tone}`}>
                            <span className="piq-stock-dot" />
                            {product.inventory ?? 0}
                          </div>
                        </td>

                        {/* Kosten */}
                        <td style={{ textAlign: 'center' }}>
                          {hasCost ? (
                            <span className="piq-cost-icon piq-cost-icon--ok" title="Kosten hinterlegt"><CheckIcon /></span>
                          ) : (
                            <span className="piq-cost-icon piq-cost-icon--missing" title="Kosten fehlen"><XIcon /></span>
                          )}
                        </td>

                        {/* Status */}
                        <td style={{ textAlign: 'center' }}>
                          {isApplied ? (
                            <span className="piq-status-chip piq-status-chip--green">Umgesetzt</span>
                          ) : rec ? (
                            <span className="piq-status-chip piq-status-chip--amber">Ausstehend</span>
                          ) : (
                            <span className="piq-status-chip piq-status-chip--gray">—</span>
                          )}
                        </td>

                        {/* Action */}
                        <td style={{ textAlign: 'right' }}>
                          <span className="piq-table-action-btn">
                            <ArrowRightIcon />
                          </span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </s-page>
  );
}
