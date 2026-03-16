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

function getReasoningText(reasoning: unknown): string {
  if (!reasoning) return '';
  if (typeof reasoning === 'string') return reasoning;
  if (typeof reasoning === 'object' && reasoning !== null) {
    const obj = reasoning as Record<string, unknown>;
    return (
      (obj.explanation as string) ||
      (obj.text as string) ||
      (obj.reasoning as string) ||
      ((obj.demand as Record<string, unknown>)?.reasoning as string) ||
      ((obj.inventory as Record<string, unknown>)?.reasoning as string) ||
      ''
    );
  }
  return String(reasoning);
}

function getStrategyText(strategy: unknown): string {
  if (!strategy) return 'ML-optimiert';
  if (typeof strategy === 'string') return strategy;
  if (typeof strategy === 'object' && strategy !== null) {
    const obj = strategy as Record<string, unknown>;
    return (obj.name as string) || (obj.strategy as string) || 'ML-optimiert';
  }
  return String(strategy);
}

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
};

export default function PricingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const suffix = useShopSuffix();
  const [selectedTab, setSelectedTab] = useState(0);

  const { data: listData, isLoading } = useQuery({
    queryKey: ['recommendations-list', selectedTab],
    queryFn: () =>
      getRecommendationsList(
        selectedTab === 0 ? 'pending' : selectedTab === 1 ? 'applied' : 'all'
      ),
  });
  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });

  const applyMutation = useMutation({
    mutationFn: async ({
      rec,
      productId,
    }: {
      rec: { id: number; product_id: number; recommended_price: number };
      productId: number;
    }) => {
      await applyPrice(productId, rec.recommended_price, rec.id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendations-list'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      showToast('Preis erfolgreich übernommen!', { duration: 3000 });
    },
    onError: (err: Error) => showToast(err.message || 'Fehler beim Übernehmen', { isError: true }),
  });
  const rejectMutation = useMutation({
    mutationFn: (recommendationId: number) =>
      rejectRecommendation(recommendationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendations-list'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      showToast('Empfehlung abgelehnt', { duration: 2000 });
    },
    onError: () => showToast('Fehler beim Ablehnen', { isError: true }),
  });

  const recs = listData?.recommendations ?? [];
  const pendingCount = stats?.recommendations_pending ?? 0;
  const appliedCount = stats?.recommendations_applied ?? 0;
  const revenue = stats?.missed_revenue?.total ?? 0;

  const filteredRecommendations = recs.map((rec: RecItem) => ({
    id: rec.id,
    productId: rec.product_id,
    productTitle: rec.product_title,
    currentPrice: rec.current_price.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    recommendedPrice: rec.recommended_price.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    priceChangePct: rec.price_change_pct ?? 0,
    confidence: rec.confidence ?? 0,
    strategy: getStrategyText(rec.strategy),
    reasoning: getReasoningText(rec.reasoning),
    status: rec.applied_at ? ('applied' as const) : ('pending' as const),
  }));

  const applyRecommendation = (rec: RecItem) => {
    applyMutation.mutate({
      rec: { id: rec.id, product_id: rec.product_id, recommended_price: rec.recommended_price },
      productId: rec.product_id,
    });
  };

  const handleReject = (recId: number) => {
    rejectMutation.mutate(recId);
  };

  return (
    <s-page title="Preisempfehlungen" back-action={JSON.stringify({ content: 'Übersicht', url: '/dashboard' + suffix })}>
    <div className="vlerafy-main">
      <div className="vlerafy-page-header">
        <s-stack direction="inline" align-items="center" justify-content="space-between">
          <div>
            <h1 className="vlerafy-page-title">Preisempfehlungen</h1>
            <p className="vlerafy-page-subtitle">
              {pendingCount} ausstehend · {appliedCount} umgesetzt ·
              {revenue > 0 ? ` +${revenue.toLocaleString('de-DE', { maximumFractionDigits: 0 })}€` : ` ${revenue.toLocaleString('de-DE', { maximumFractionDigits: 0 })}€`} Potenzial
            </p>
          </div>
        </s-stack>
      </div>

      <div className="vlerafy-tabs vlerafy-tabs-mb">
        {['Ausstehend', 'Umgesetzt', 'Alle'].map((tab, index) => (
          <button
            key={tab}
            type="button"
            className={`vlerafy-tab ${selectedTab === index ? 'vlerafy-tab--active' : ''}`}
            onClick={() => setSelectedTab(index)}
          >
            {tab}
          </button>
        ))}
      </div>

      {filteredRecommendations.length === 0 ? (
        <div className="vlerafy-empty-state">
          <div className="vlerafy-empty-state-icon">💰</div>
          <p className="vlerafy-empty-state-title">
            {isLoading ? 'Lade Empfehlungen...' : selectedTab === 0 ? 'Alle Empfehlungen bearbeitet 🎉' : 'Keine Empfehlungen'}
          </p>
          <p className="vlerafy-empty-state-text">
            {selectedTab === 0
              ? 'Großartig! Alle Preisempfehlungen wurden verarbeitet.'
              : 'Sobald Produkte analysiert wurden, erscheinen hier deine Preisempfehlungen.'}
          </p>
          <s-button
            variant="primary"
            onClick={() => router.push(`/dashboard/products${suffix}`)}
          >
            Produkte synchronisieren
          </s-button>
        </div>
      ) : (
        <div className="vlerafy-table-card">
          <div className="vlerafy-table-wrapper">
            <table className="vlerafy-table">
              <thead>
                <tr>
                  <th>Produkt</th>
                  <th>Aktueller Preis</th>
                  <th>Empfehlung</th>
                  <th>Änderung</th>
                  <th>Sicherheit</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredRecommendations.map((rec) => {
                  const rawRec = recs.find((r: RecItem) => r.id === rec.id) as RecItem | undefined;
                  return (
                    <tr key={rec.id}>
                      <td>
                        <div>
                          <p className="vlerafy-product-title">{rec.productTitle}</p>
                          <p className="vlerafy-kpi-label vlerafy-mt-2">
                            {rec.strategy}
                          </p>
                        </div>
                      </td>
                      <td className="vlerafy-table-price">{rec.currentPrice} €</td>
                      <td className="vlerafy-table-price vlerafy-price-recommended-cell">
                        {rec.recommendedPrice} €
                      </td>
                      <td>
                        <span
                          className={
                            rec.priceChangePct > 0
                              ? 'vlerafy-price-change-badge vlerafy-price-change-badge--up'
                              : rec.priceChangePct < 0
                                ? 'vlerafy-price-change-badge vlerafy-price-change-badge--down'
                                : 'vlerafy-price-change-badge vlerafy-price-change-badge--neutral'
                          }
                        >
                          {rec.priceChangePct > 0 ? '▲' : rec.priceChangePct < 0 ? '▼' : '='}
                          {Math.abs(rec.priceChangePct).toFixed(2)}%
                        </span>
                      </td>
                      <td>
                        <div className="vlerafy-confidence-bar vlerafy-confidence-bar--sm">
                          <div
                            className="vlerafy-confidence-fill"
                            style={{ width: `${rec.confidence * 100}%` }}
                          />
                        </div>
                        <p className="vlerafy-kpi-label vlerafy-mt-3">
                          {Math.round(rec.confidence * 100)}%
                        </p>
                      </td>
                      <td>
                        {rec.status === 'pending' ? (
                          <s-badge tone="attention">Ausstehend</s-badge>
                        ) : rec.status === 'applied' ? (
                          <s-badge tone="success">Umgesetzt</s-badge>
                        ) : (
                          <s-badge tone="info">Abgelehnt</s-badge>
                        )}
                      </td>
                      <td>
                        {rec.status === 'pending' && rawRec && (
                          <s-stack direction="inline" gap="2">
                            <s-button
                              variant="primary"
                              size="slim"
                              loading={applyMutation.isPending}
                              onClick={() => applyRecommendation(rawRec)}
                            >
                              Übernehmen
                            </s-button>
                            <s-button
                              variant="plain"
                              size="slim"
                              onClick={() => handleReject(rec.id)}
                            >
                              Ablehnen
                            </s-button>
                          </s-stack>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
    </s-page>
  );
}

// ✅ BFS [Punkt 2, 8] erledigt — s-page + back-action auf Preisempfehlungen
