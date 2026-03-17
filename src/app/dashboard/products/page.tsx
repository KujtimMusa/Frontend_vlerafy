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
    <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      <path d="M2.5 2.5l6 6M8.5 2.5l-6 6" />
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
  return raw
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function stockLevel(qty: number): { label: string; tone: string } {
  if (qty === 0) return { label: 'Ausverkauft', tone: 'red' };
  if (qty <= 10) return { label: 'Niedrig', tone: 'amber' };
  return { label: 'Verfügbar', tone: 'green' };
}

function timeAgo(iso: string | null): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return 'Heute';
  if (days === 1) return 'Gestern';
  if (days < 7) return `vor ${days} Tagen`;
  if (days < 30) return `vor ${Math.floor(days / 7)} Wo.`;
  return `vor ${Math.floor(days / 30)} Mon.`;
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

  /* ── Recommendation lookup ── */
  type Rec = NonNullable<typeof recsData>['recommendations'][number];
  const recMap = new Map<number, Rec>();
  (recsData?.recommendations ?? []).forEach((r) => recMap.set(r.product_id, r));

  /* ── Derived counts ── */
  const totalProducts      = products.length || (stats?.products_count ?? 0);
  const withRecommendation = recMap.size || (stats?.products_with_recommendations ?? 0);
  const noStock            = products.filter((p) => (p.inventory ?? 0) === 0).length;
  const withCost           = products.filter((p) => p.cost != null && p.cost > 0).length;
  const noCost             = totalProducts - withCost;

  /* ── Filter ── */
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

  /* ── Empty State ── */
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

        {/* ── Status-Banners ── */}
        {syncMutation.isPending && (
          <s-banner tone="info">
            <s-paragraph>Produkte werden synchronisiert…</s-paragraph>
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

        {/* ══ KPI Summary Strip ══ */}
        <div className="piq-prod-kpi-strip">
          <div className="piq-prod-kpi">
            <div className="piq-prod-kpi-val">{totalProducts}</div>
            <div className="piq-prod-kpi-lbl">Produkte gesamt</div>
          </div>
          <div className="piq-prod-kpi-sep" />
          <div className="piq-prod-kpi">
            <div className="piq-prod-kpi-val piq-prod-kpi-val--amber">{withRecommendation}</div>
            <div className="piq-prod-kpi-lbl">Mit Empfehlung</div>
          </div>
          <div className="piq-prod-kpi-sep" />
          <div className="piq-prod-kpi">
            <div className="piq-prod-kpi-val piq-prod-kpi-val--green">
              {withCost}/{totalProducts}
            </div>
            <div className="piq-prod-kpi-lbl">Kosten hinterlegt</div>
          </div>
          <div className="piq-prod-kpi-sep" />
          <div className="piq-prod-kpi">
            <div className="piq-prod-kpi-val piq-prod-kpi-val--red">{noStock}</div>
            <div className="piq-prod-kpi-lbl">Ausverkauft</div>
          </div>
        </div>

        {/* ══ TABELLE ══ */}
        <div className="piq-table-card">

          {/* ── Tab-Bar ── */}
          <div className="piq-tab-bar">
            <div className="piq-tabs" role="tablist">
              <button role="tab" aria-selected={activeTab === 'all'}
                className={`piq-tab${activeTab === 'all' ? ' piq-tab--active' : ''}`}
                onClick={() => setActiveTab('all')}
              >
                Alle <span className="piq-tab-badge">{totalProducts}</span>
              </button>
              <button role="tab" aria-selected={activeTab === 'recommended'}
                className={`piq-tab${activeTab === 'recommended' ? ' piq-tab--active' : ''}`}
                onClick={() => setActiveTab('recommended')}
              >
                Mit Empfehlung <span className="piq-tab-badge piq-tab-badge--amber">{withRecommendation}</span>
              </button>
              <button role="tab" aria-selected={activeTab === 'no-stock'}
                className={`piq-tab${activeTab === 'no-stock' ? ' piq-tab--active' : ''}`}
                onClick={() => setActiveTab('no-stock')}
              >
                Kein Lagerbestand <span className="piq-tab-badge piq-tab-badge--red">{noStock}</span>
              </button>
              <button role="tab" aria-selected={activeTab === 'no-cost'}
                className={`piq-tab${activeTab === 'no-cost' ? ' piq-tab--active' : ''}`}
                onClick={() => setActiveTab('no-cost')}
              >
                Ohne Kosten <span className="piq-tab-badge">{noCost}</span>
              </button>
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
            <table className="piq-table piq-table--rich">
              <thead>
                <tr>
                  <th>Produkt</th>
                  <th style={{ textAlign: 'right' }}>Preis</th>
                  <th style={{ textAlign: 'center' }}>Lagerbestand</th>
                  <th style={{ textAlign: 'center' }}>Kosten</th>
                  <th style={{ textAlign: 'center' }}>Empfehlung</th>
                  <th style={{ textAlign: 'right' }}>Potenzial</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.length === 0 ? (
                  <tr>
                    <td colSpan={7}>
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
                    const potential = rec && rec.recommended_price > rec.current_price
                      ? rec.recommended_price - rec.current_price
                      : 0;
                    const isApplied = rec?.applied_at != null;

                    return (
                      <tr
                        key={product.id}
                        tabIndex={0}
                        onClick={() => router.push(`/dashboard/products/${product.id}${suffix}`)}
                        onKeyDown={(e) => e.key === 'Enter' && router.push(`/dashboard/products/${product.id}${suffix}`)}
                      >
                        {/* Produkt */}
                        <td>
                          <div className="piq-prod-cell">
                            <div className="piq-product-avatar">
                              {product.image
                                ? <img src={product.image} alt={product.title} />
                                : <span>{product.title.charAt(0)}</span>
                              }
                            </div>
                            <div className="piq-prod-info">
                              <span className="piq-product-name">{product.title}</span>
                              {rec && (
                                <span className="piq-prod-meta">
                                  {readableStrategy(rec.strategy)} · {Math.round(rec.confidence * 100)}%
                                </span>
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
                              <span className="piq-price-rec">
                                → {rec.recommended_price.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €
                              </span>
                            )}
                          </div>
                        </td>

                        {/* Lagerbestand */}
                        <td style={{ textAlign: 'center' }}>
                          <div className={`piq-stock-pill piq-stock-pill--${stock.tone}`}>
                            <span className="piq-stock-dot" />
                            {product.inventory ?? 0} Stk.
                          </div>
                          <div className="piq-stock-label">{stock.label}</div>
                        </td>

                        {/* Kosten */}
                        <td style={{ textAlign: 'center' }}>
                          {hasCost ? (
                            <span className="piq-cost-badge piq-cost-badge--ok">
                              <CheckIcon /> Hinterlegt
                            </span>
                          ) : (
                            <span className="piq-cost-badge piq-cost-badge--missing">
                              <XIcon /> Fehlt
                            </span>
                          )}
                        </td>

                        {/* Empfehlung */}
                        <td style={{ textAlign: 'center' }}>
                          {isApplied ? (
                            <div>
                              <s-badge tone="success">Umgesetzt</s-badge>
                              <div className="piq-rec-time">{timeAgo(rec!.applied_at)}</div>
                            </div>
                          ) : rec ? (
                            <div>
                              <s-badge tone="warning">Ausstehend</s-badge>
                              <div className="piq-rec-time">
                                {Math.round(rec.confidence * 100)}% sicher
                              </div>
                            </div>
                          ) : (
                            <span className="piq-table-muted">—</span>
                          )}
                        </td>

                        {/* Potenzial */}
                        <td style={{ textAlign: 'right' }}>
                          {potential > 0 ? (
                            <span className="piq-potential-val">
                              +€{potential.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </span>
                          ) : (
                            <span className="piq-table-muted">—</span>
                          )}
                        </td>

                        {/* Action */}
                        <td style={{ textAlign: 'right' }}>
                          <span className="piq-table-action-btn">
                            Ansehen <ArrowRightIcon />
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
