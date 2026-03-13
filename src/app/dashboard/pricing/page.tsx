'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import {
  getRecommendationsList,
  applyPrice,
  rejectRecommendation,
  getDashboardStats,
} from '@/lib/api';
import {
  Page,
  Card,
  Text,
  Badge,
  Button,
  BlockStack,
  InlineStack,
  ProgressBar,
  EmptyState,
  Tabs,
} from '@shopify/polaris';
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

export default function PricingPage() {
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
      rec: (typeof recs)[0];
      productId: number;
    }) => {
      await applyPrice(productId, rec.recommended_price, rec.id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendations-list'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      showToast('Preis erfolgreich übernommen!', { duration: 3000 });
    },
    onError: (err) => showToast(err.message || 'Fehler beim Übernehmen', { isError: true }),
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

  const tabs = [
    { id: 'pending', content: 'Ausstehend', panelID: 'pending' },
    { id: 'applied', content: 'Umgesetzt', panelID: 'applied' },
    { id: 'all', content: 'Alle', panelID: 'all' },
  ];

  return (
    <Page
      title="Preisempfehlungen"
      subtitle={`${pending} ausstehend · ${applied} umgesetzt · ${totalPotential.toFixed(0)}€ Potenzial`}
    >
      <BlockStack gap="500">
        <Tabs tabs={tabs} selected={activeTab} onSelect={setActiveTab} />

        <BlockStack gap="300">
          {recs.map((rec) => (
            <Card key={rec.id}>
              <BlockStack gap="300">
                <InlineStack align="space-between" blockAlign="start" gap="400">
                  <BlockStack gap="100">
                    <Text as="h2" variant="headingMd">{rec.product_title}</Text>
                    <InlineStack gap="400">
                      <Text as="p" tone="subdued">
                        Aktuell: {formatPrice(rec.current_price)}
                      </Text>
                      <Text as="span" variant="headingSm" tone="success">
                        → Empfohlen: {formatPrice(rec.recommended_price)}
                      </Text>
                      <Badge tone="success">
                        {`+${formatPrice(rec.recommended_price - rec.current_price)} mehr`}
                      </Badge>
                    </InlineStack>
                  </BlockStack>
                  {!rec.applied_at && (
                    <InlineStack gap="200">
                      <Button
                        variant="primary"
                        size="slim"
                        onClick={() =>
                          applyMutation.mutate({
                            rec,
                            productId: rec.product_id,
                          })
                        }
                        loading={applyMutation.isPending}
                      >
                        Übernehmen
                      </Button>
                      <Button
                        variant="plain"
                        tone="critical"
                        size="slim"
                        onClick={() => rejectMutation.mutate(rec.id)}
                      >
                        Ablehnen
                      </Button>
                    </InlineStack>
                  )}
                </InlineStack>

                {rec.reasoning && (
                  <Text as="p" tone="subdued" variant="bodySm">
                    {rec.reasoning}
                  </Text>
                )}

                <InlineStack gap="300" blockAlign="center">
                  <Text as="span" variant="bodySm" tone="subdued">
                    Analyse-Sicherheit:
                  </Text>
                  <div style={{ flex: 1, maxWidth: 200 }}>
                    <ProgressBar
                      progress={rec.confidence * 100}
                      size="small"
                    />
                  </div>
                  <Text as="span" variant="bodySm" fontWeight="semibold">
                    {Math.round(rec.confidence * 100)}%
                  </Text>
                </InlineStack>
              </BlockStack>
            </Card>
          ))}
        </BlockStack>

        {!isLoading && recs.length === 0 && (
          <EmptyState
            heading={
              activeTab === 0 ? 'Alle Empfehlungen bearbeitet 🎉' : 'Keine Empfehlungen'
            }
            image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
            action={{
              content: 'Produkte ansehen',
              url: `/dashboard/products${suffix}`,
            }}
          >
            {activeTab === 0
              ? 'Großartig! Alle Preisempfehlungen wurden verarbeitet.'
              : 'Generiere Preisempfehlungen in der Produktübersicht.'}
          </EmptyState>
        )}
      </BlockStack>
    </Page>
  );
}
