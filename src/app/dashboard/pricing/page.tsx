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

function formatPrice(v: number): string {
  return new Intl.NumberFormat('de-DE', {
    style: 'currency',
    currency: 'EUR',
  }).format(v);
}

const TABS = [
  { id: 'pending', content: 'Ausstehend', index: 0 },
  { id: 'applied', content: 'Umgesetzt', index: 1 },
  { id: 'all', content: 'Alle', index: 2 },
];

export default function PricingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const suffix = useShopSuffix();
  const [activeTab, setActiveTab] = useState(0);

  const { data: listData, isLoading } = useQuery({
    queryKey: ['recommendations-list', activeTab],
    queryFn: () =>
      getRecommendationsList(
        activeTab === 0 ? 'pending' : activeTab === 1 ? 'applied' : 'all'
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
  const pending = stats?.recommendations_pending ?? 0;
  const applied = stats?.recommendations_applied ?? 0;
  const totalPotential = stats?.missed_revenue?.total ?? 0;

  return (
    <div className="vlerafy-main">
      <div className="vlerafy-page-header">
        <h1 className="vlerafy-page-title">Preisempfehlungen</h1>
        <p className="vlerafy-page-subtitle">
          {pending} ausstehend · {applied} umgesetzt · {totalPotential.toFixed(0)}€ Potenzial
        </p>
      </div>

      <div className="vlerafy-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`vlerafy-tab ${activeTab === tab.index ? 'vlerafy-tab--active' : ''}`}
            onClick={() => setActiveTab(tab.index)}
          >
            {tab.content}
          </button>
        ))}
      </div>

      <s-stack direction="block" gap="3">
        {recs.map((rec) => (
          <s-section key={rec.id}>
            <s-stack direction="block" gap="3">
              <s-stack
                direction="inline"
                style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}
              >
                <s-stack direction="block" gap="1">
                  <s-heading size="md">{rec.product_title}</s-heading>
                  <s-stack direction="inline" gap="4" style={{ alignItems: 'center', flexWrap: 'wrap' }}>
                    <s-paragraph tone="subdued">Aktuell: {formatPrice(rec.current_price)}</s-paragraph>
                    <s-text variant="headingSm" tone="success">
                      → Empfohlen: {formatPrice(rec.recommended_price)}
                    </s-text>
                    <s-badge tone="success">
                      +{formatPrice(rec.recommended_price - rec.current_price)} mehr
                    </s-badge>
                  </s-stack>
                </s-stack>
                {!rec.applied_at && (
                  <s-stack direction="inline" gap="2">
                    <s-button
                      variant="primary"
                      size="slim"
                      loading={applyMutation.isPending}
                      onClick={() =>
                        applyMutation.mutate({
                          rec,
                          productId: rec.product_id,
                        })
                      }
                    >
                      Übernehmen
                    </s-button>
                    <s-button
                      variant="plain"
                      size="slim"
                      onClick={() => rejectMutation.mutate(rec.id)}
                      style={{ color: 'var(--v-critical)' }}
                    >
                      Ablehnen
                    </s-button>
                  </s-stack>
                )}
              </s-stack>

              {rec.reasoning && (
                <s-paragraph tone="subdued" style={{ fontSize: 13 }}>
                  {rec.reasoning}
                </s-paragraph>
              )}

              <s-stack direction="inline" style={{ alignItems: 'center', gap: 12 }}>
                <s-paragraph tone="subdued" style={{ fontSize: 13 }}>
                  Analyse-Sicherheit:
                </s-paragraph>
                <div style={{ flex: 1, maxWidth: 200 }}>
                  <div className="vlerafy-progress">
                    <div
                      className="vlerafy-progress-bar"
                      style={{ width: `${rec.confidence * 100}%` }}
                    />
                  </div>
                </div>
                <s-text font-weight="600" style={{ fontSize: 13 }}>
                  {Math.round(rec.confidence * 100)}%
                </s-text>
              </s-stack>
            </s-stack>
          </s-section>
        ))}
      </s-stack>

      {!isLoading && recs.length === 0 && (
        <div className="vlerafy-empty-state">
          <div className="vlerafy-empty-state-icon">💰</div>
          <p className="vlerafy-empty-state-title">
            {activeTab === 0 ? 'Alle Empfehlungen bearbeitet 🎉' : 'Keine Empfehlungen'}
          </p>
          <p className="vlerafy-empty-state-text">
            {activeTab === 0
              ? 'Großartig! Alle Preisempfehlungen wurden verarbeitet.'
              : 'Generiere Preisempfehlungen in der Produktübersicht.'}
          </p>
          <s-button
            variant="primary"
            onClick={() => router.push(`/dashboard/products${suffix}`)}
          >
            Produkte ansehen
          </s-button>
        </div>
      )}
    </div>
  );
}
