'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams, useRouter } from 'next/navigation';
import {
  getRecommendationsList,
  applyPrice,
  rejectRecommendation,
  getDashboardStats,
} from '@/lib/api';
import { showToast } from '@/lib/toast';

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
  const q = p.toString();
  return q ? `?${q}` : '';
}

function ArrowRight() {
  return (
    <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      <path d="M3.5 2l4 3.5-4 3.5" />
    </svg>
  );
}

function formatEuro(v: number): string {
  return v.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
}

const truncate = (s: string, max = 38) =>
  s.length > max ? s.slice(0, max) + '…' : s;

type FilterTab = 'pending' | 'applied' | 'all';

type RecItem = {
  id: number;
  product_id: number;
  product_title: string;
  current_price: number;
  recommended_price: number;
  price_change_pct: number;
  confidence: number;
  strategy: string;
  reasoning: unknown;
  applied_at: string | null;
  rejected_at?: string | null;
  sales_30d?: number | null;
  sales_7d?: number | null;
};

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 7.5l3 3 5-6" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4l6 6M10 4l-6 6" />
    </svg>
  );
}

function PendingIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 19 19" fill="none" stroke="#d97706" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9.5" cy="9.5" r="7.5" />
      <path d="M9.5 5.5v4.5l3 1.5" />
    </svg>
  );
}

function AppliedIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 19 19" fill="none" stroke="#059669" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9.5" cy="9.5" r="7.5" />
      <path d="M6.5 9.5l2 2 4-5" />
    </svg>
  );
}

function RevenueIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 19 19" fill="none" stroke="#4f46e5" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.5 2v15M14 6.5c0-1.2-.9-2.2-2.2-2.2H7.5a2.2 2.2 0 0 0 0 4.4h4a2.2 2.2 0 0 1 0 4.4H6" />
    </svg>
  );
}

export default function PricingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const suffix = useShopSuffix();
  const [activeTab, setActiveTab] = useState<FilterTab>('pending');
  const [searchQuery, setSearchQuery] = useState('');

  const { data: listData, isLoading } = useQuery({
    queryKey: ['recommendations-list', activeTab],
    queryFn: () => getRecommendationsList(activeTab),
  });
  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });

  const applyMutation = useMutation({
    mutationFn: async ({ rec }: { rec: RecItem }) => {
      await applyPrice(rec.product_id, rec.recommended_price, rec.id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendations-list'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      showToast('Preis übernommen!', { duration: 3000 });
    },
    onError: (err: Error) => showToast(err.message || 'Fehler', { isError: true }),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: number) => rejectRecommendation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendations-list'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      showToast('Empfehlung abgelehnt', { duration: 2000 });
    },
    onError: () => showToast('Fehler beim Ablehnen', { isError: true }),
  });

  const allRecs: RecItem[] = listData?.recommendations ?? [];
  const pendingCount = stats?.recommendations_pending ?? 0;
  const appliedCount = stats?.recommendations_applied ?? 0;
  const revenue = stats?.missed_revenue?.total ?? 0;

  const byProduct = new Map<number, RecItem>();
  for (const r of allRecs) {
    const existing = byProduct.get(r.product_id);
    if (!existing || new Date(r.applied_at ?? '9999') > new Date(existing.applied_at ?? '9999')) {
      byProduct.set(r.product_id, r);
    }
  }
  let productRecs = Array.from(byProduct.values());

  if (searchQuery.trim()) {
    const q = searchQuery.toLowerCase();
    productRecs = productRecs.filter(r => r.product_title?.toLowerCase().includes(q));
  }

  productRecs.sort((a, b) => Math.abs(b.price_change_pct ?? 0) - Math.abs(a.price_change_pct ?? 0));

  const handleSearch = (e: unknown) => {
    const evt = e as { target?: { value?: string }; detail?: string };
    setSearchQuery(String(evt.target?.value ?? evt.detail ?? ''));
  };

  return (
    <s-page title="Empfehlungen">
      <div className="piq-dashboard">

        {/* ══ 3 KPI-Cards ══ */}
        <div className="piq-hero-grid">
          <div className="piq-hero-card piq-hero-card--compact">
            <div className="piq-hero-icon"><PendingIcon /></div>
            <div className="piq-hero-lbl">Ausstehend</div>
            <div className="piq-hero-val">{pendingCount}</div>
            <div className="piq-hero-sub">Empfehlungen offen</div>
          </div>
          <div className="piq-hero-card piq-hero-card--compact">
            <div className="piq-hero-icon"><AppliedIcon /></div>
            <div className="piq-hero-lbl">Umgesetzt</div>
            <div className="piq-hero-val">{appliedCount}</div>
            <div className="piq-hero-sub">Preise übernommen</div>
          </div>
          <div className="piq-hero-card piq-hero-card--compact">
            <div className="piq-hero-icon"><RevenueIcon /></div>
            <div className="piq-hero-lbl">Potenzial</div>
            <div className="piq-hero-val">
              {revenue >= 0 ? '+' : ''}{Math.abs(Math.round(revenue)).toLocaleString('de-DE')} €
            </div>
            <div className="piq-hero-sub">möglicher mehr Umsatz / Monat</div>
          </div>
        </div>

        {/* ══ Empfehlungsliste ══ */}
        <div className="piq-chart-section">
          <div className="piq-chart-header">
            <div className="piq-chart-title">Preisempfehlungen pro Produkt</div>
            <span className="piq-chart-badge">{productRecs.length} Produkte</span>
          </div>

          {/* Filter-Tabs + Suche */}
          <div className="piq-rec-toolbar">
            <div className="piq-rec-tabs">
              {([
                ['pending', 'Ausstehend'],
                ['applied', 'Umgesetzt'],
                ['all', 'Alle'],
              ] as [FilterTab, string][]).map(([key, label]) => (
                <button
                  key={key}
                  className={`piq-rec-tab ${activeTab === key ? 'piq-rec-tab--active' : ''}`}
                  onClick={() => setActiveTab(key)}
                >
                  {label}
                </button>
              ))}
            </div>
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
                onChange={handleSearch}
                onInput={handleSearch}
              />
            </div>
          </div>

          {/* Liste */}
          {isLoading ? (
            <div className="piq-rec-loading"><s-spinner size="small" /></div>
          ) : productRecs.length === 0 ? (
            <div className="piq-toprec-empty">
              <div className="piq-toprec-empty-title">
                {searchQuery ? 'Kein Produkt gefunden' : activeTab === 'pending' ? 'Alle Empfehlungen bearbeitet' : 'Keine Empfehlungen'}
              </div>
              <div className="piq-toprec-empty-sub">
                {searchQuery
                  ? 'Ändere deinen Suchbegriff.'
                  : activeTab === 'pending'
                    ? 'Alle Preisempfehlungen wurden bearbeitet.'
                    : 'Sobald Produkte analysiert werden, erscheinen hier Empfehlungen.'}
              </div>
            </div>
          ) : (
            <div className="piq-rec-list">
              {productRecs.map((rec) => {
                const diff = rec.recommended_price - rec.current_price;
                const diffPct = rec.price_change_pct ?? (rec.current_price > 0 ? (diff / rec.current_price) * 100 : 0);
                const isUp = diffPct > 0;
                const isPending = !rec.applied_at && !rec.rejected_at;
                const isApplied = !!rec.applied_at;
                const confidencePct = Math.round((rec.confidence ?? 0) * 100);

                return (
                  <div key={rec.product_id} className="piq-rec-row">
                    <div
                      className="piq-rec-row-main"
                      role="button"
                      tabIndex={0}
                      onClick={() => router.push(`/dashboard/products/${rec.product_id}${suffix}`)}
                      onKeyDown={(e) => e.key === 'Enter' && router.push(`/dashboard/products/${rec.product_id}${suffix}`)}
                    >
                      <div className="piq-rec-product">
                        <div className="piq-rec-product-name">{truncate(rec.product_title)}</div>
                        <div className="piq-rec-product-prices">
                          <span className="piq-rec-price-current">{formatEuro(rec.current_price)}</span>
                          <span className="piq-rec-arrow">→</span>
                          <span className="piq-rec-price-new">{formatEuro(rec.recommended_price)}</span>
                        </div>
                      </div>

                      <div className="piq-rec-meta">
                        <span className={`piq-rec-change ${isUp ? 'piq-rec-change--up' : 'piq-rec-change--down'}`}>
                          {isUp ? '▲' : '▼'} {Math.abs(diffPct).toFixed(1)}%
                        </span>
                        <span className="piq-rec-confidence">
                          <span className="piq-rec-conf-bar">
                            <span className="piq-rec-conf-fill" style={{ width: `${confidencePct}%` }} />
                          </span>
                          <span className="piq-rec-conf-txt">{confidencePct}%</span>
                        </span>
                        {isApplied && <span className="piq-rec-status piq-rec-status--applied">Umgesetzt</span>}
                        {!isPending && !isApplied && <span className="piq-rec-status piq-rec-status--rejected">Abgelehnt</span>}
                      </div>

                      <div className="piq-rec-go"><ArrowRight /></div>
                    </div>

                    {isPending && (
                      <div className="piq-rec-actions">
                        <button
                          className="piq-rec-action piq-rec-action--apply"
                          onClick={() => applyMutation.mutate({ rec })}
                          disabled={applyMutation.isPending}
                          title="Preis übernehmen"
                        >
                          <CheckIcon /> Übernehmen
                        </button>
                        <button
                          className="piq-rec-action piq-rec-action--reject"
                          onClick={() => rejectMutation.mutate(rec.id)}
                          disabled={rejectMutation.isPending}
                          title="Empfehlung ablehnen"
                        >
                          <XIcon /> Ablehnen
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

      </div>
    </s-page>
  );
}
