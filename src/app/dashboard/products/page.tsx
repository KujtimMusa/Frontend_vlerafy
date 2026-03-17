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
  const shop   = searchParams.get('shop')     ?? (typeof window !== 'undefined' ? localStorage.getItem('shop_domain')      : null) ?? '';
  const host   = searchParams.get('host')     ?? (typeof window !== 'undefined' ? localStorage.getItem('shopify_host')     : null) ?? '';
  const shopId = searchParams.get('shop_id') ?? (typeof window !== 'undefined' ? localStorage.getItem('current_shop_id')  : null) ?? '';
  const idToken = searchParams.get('id_token') ?? '';
  const p = new URLSearchParams();
  if (shop)    p.set('shop',     shop);
  if (host)    p.set('host',     host);
  if (shopId)  p.set('shop_id',  shopId);
  if (idToken) p.set('id_token', idToken);
  return p.toString() ? `?${p.toString()}` : '';
}

function TotalIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#2d6bc4" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="6" height="6" rx="1.5" />
      <rect x="10" y="2" width="6" height="6" rx="1.5" />
      <rect x="2" y="10" width="6" height="6" rx="1.5" />
      <rect x="10" y="10" width="6" height="6" rx="1.5" />
    </svg>
  );
}

function RecommendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#d97706" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 1.5v15M12.5 5.5c0-1.1-.9-2-2-2H7.5a2 2 0 0 0 0 4h3a2 2 0 0 1 0 4H6" />
    </svg>
  );
}

function StockIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#dc2626" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3h3l2 9h7l1.5-6H6.5" />
      <circle cx="9" cy="15.5" r="1" />
      <circle cx="14" cy="15.5" r="1" />
      <path d="M1.5 1.5l15 15" />
    </svg>
  );
}

function RevenueIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#059669" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 13l4-5 4 3.5 4-7.5" />
      <circle cx="15" cy="3.5" r="1.5" fill="#059669" stroke="none" />
    </svg>
  );
}

function ArrowRightIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      <path d="M4.5 2.5l4 4-4 4" />
    </svg>
  );
}

function SyncIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 2.5A5.5 5.5 0 0 0 2 7" />
      <path d="M2 10.5A5.5 5.5 0 0 0 11 6" />
      <path d="M11 0.5v2h-2" />
      <path d="M2 12.5v-2h2" />
    </svg>
  );
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
  const filteredProducts  = (products ?? []).filter((p) =>
    p.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const totalProducts      = stats?.products_count ?? products.length;
  const withRecommendation = stats?.products_with_recommendations ?? productIdsWithRec.size;
  const noStock            = (products ?? []).filter((p) => (p.inventory ?? 0) === 0).length;
  const potentialRevenue   = stats?.missed_revenue?.total ?? 0;
  const revenue            = `+€${Math.abs(potentialRevenue).toLocaleString('de-DE', { maximumFractionDigits: 0 })}`;
  const recPercent         = totalProducts > 0 ? Math.round((withRecommendation / totalProducts) * 100) : 0;

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

  const backAction = JSON.stringify({ content: 'Übersicht', url: '/dashboard' + suffix });

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

        {/* ── Header Bar ── */}
        <div className="piq-prod-header">
          <div className="piq-prod-stats">
            <span className="piq-prod-stat">{totalProducts} Produkte</span>
            <span className="piq-prod-stat-sep">·</span>
            <span className="piq-prod-stat piq-prod-stat--amber">{withRecommendation} mit Empfehlung</span>
            {noStock > 0 && (
              <>
                <span className="piq-prod-stat-sep">·</span>
                <span className="piq-prod-stat" style={{ color: 'var(--red)' }}>{noStock} kein Lager</span>
              </>
            )}
          </div>
          <div className="piq-prod-actions">
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
          </div>
        </div>

        {/* ── KPI Strip — 4 Cards ── */}
        <div className="piq-kpi piq-kpi--4col">

          <div className="piq-kc piq-kc--navy">
            <div className="piq-kc-icon piq-kc-icon--navy"><TotalIcon /></div>
            <div className="piq-kc-lbl">Produkte gesamt</div>
            <div className="piq-kc-val">{totalProducts}</div>
            <div className="piq-kc-sub">synchronisierte Artikel</div>
          </div>

          <div className="piq-kc piq-kc--amber">
            <div className="piq-kc-icon piq-kc-icon--amber"><RecommendIcon /></div>
            <div className="piq-kc-lbl">Mit Empfehlung</div>
            <div className="piq-kc-val piq-kc-val--amber">{withRecommendation}</div>
            <div className="piq-kc-sub">{recPercent}% aller Produkte</div>
          </div>

          <div className="piq-kc piq-kc--red">
            <div className="piq-kc-icon piq-kc-icon--red"><StockIcon /></div>
            <div className="piq-kc-lbl">Kein Lagerbestand</div>
            <div className="piq-kc-val" style={{ color: 'var(--red)' }}>{noStock}</div>
            <div className="piq-kc-sub">Produkte prüfen</div>
          </div>

          <div className="piq-kc piq-kc--green">
            <div className="piq-kc-icon piq-kc-icon--green"><RevenueIcon /></div>
            <div className="piq-kc-lbl">Möglicher Mehrumsatz</div>
            <div className="piq-kc-val" style={{ color: 'var(--green)' }}>{revenue}</div>
            <div className="piq-kc-sub">bei Umsetzung aller Empfehlungen</div>
          </div>

        </div>

        {/* ── Tabelle ── */}
        <div className="piq-table-card">
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

          <div style={{ overflowX: 'auto' }}>
            <table className="piq-table">
              <thead>
                <tr>
                  <th>Produkt</th>
                  <th>Preis</th>
                  <th>Lagerbestand</th>
                  <th>Empfehlung</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.length === 0 ? (
                  <tr>
                    <td colSpan={5}>
                      <div className="piq-table-empty">
                        <div className="piq-table-empty-icon">🔍</div>
                        <s-paragraph>Keine Ergebnisse für &bdquo;{searchQuery}&ldquo;</s-paragraph>
                        <s-paragraph tone="subdued">Versuche einen anderen Suchbegriff.</s-paragraph>
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
                      <td className="piq-table-price">
                        {product.price != null
                          ? `${product.price.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`
                          : '—'}
                      </td>
                      <td>
                        {(product.inventory ?? 0) === 0
                          ? <s-badge tone="critical">0 Stück</s-badge>
                          : <s-badge tone="success">{product.inventory} Stück</s-badge>
                        }
                      </td>
                      <td>
                        {productIdsWithRec.has(product.id)
                          ? <s-badge tone="warning">Ausstehend</s-badge>
                          : <span className="piq-table-muted">—</span>
                        }
                      </td>
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

        {/* Sync hint */}
        {!syncMutation.isPending && products.length > 0 && (
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <s-button variant="plain" size="slim" onClick={handleSync}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <SyncIcon />
                Neu synchronisieren
              </span>
            </s-button>
          </div>
        )}

      </div>
    </s-page>
  );
}
