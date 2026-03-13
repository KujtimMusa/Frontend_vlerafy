'use client';

import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import {
  getDashboardStats,
  getEngineStatus,
  fetchProducts,
  getMarginHistory,
} from '@/lib/api';
import {
  Page,
  Card,
  Text,
  Badge,
  BlockStack,
  InlineGrid,
  InlineStack,
  SkeletonPage,
} from '@shopify/polaris';
import { AlertCircleIcon, CheckCircleIcon, ChartLineIcon } from '@shopify/polaris-icons';
import { StatKarte } from '@/components/StatKarte';
import { FortschrittsCard } from '@/components/FortschrittsCard';
import { PreisverlaufChart } from '@/components/PreisverlaufChart';

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

export default function AnalyticsPage() {
  const suffix = useShopSuffix();
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });
  const { data: engineStatus } = useQuery({
    queryKey: ['engine-status'],
    queryFn: getEngineStatus,
  });
  const { data: products = [] } = useQuery({
    queryKey: ['products'],
    queryFn: () => fetchProducts(),
  });
  const topProduct = products[0];
  const { data: historyData } = useQuery({
    queryKey: ['margin-history', topProduct?.shopify_product_id],
    queryFn: () =>
      getMarginHistory(topProduct!.shopify_product_id, 30),
    enabled: !!topProduct?.shopify_product_id,
  });

  const chartData =
    historyData?.history?.map((h) => ({
      date: new Date(h.date).toLocaleDateString('de-DE', {
        day: '2-digit',
        month: '2-digit',
      }),
      price: h.selling_price,
    })) ?? [];

  if (isLoading) return <SkeletonPage />;

  return (
    <Page
      title="Analysen"
      primaryAction={{
        content: 'Produkte optimieren',
        url: `/dashboard/pricing${suffix}`,
      }}
    >
      <BlockStack gap="500">
        <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="400">
          <StatKarte
            value={stats?.recommendations_pending ?? 0}
            label="Ausstehend"
            icon={<AlertCircleIcon />}
            tone="warning"
          />
          <StatKarte
            value={stats?.recommendations_applied ?? 0}
            label="Umgesetzt"
            icon={<CheckCircleIcon />}
            tone="success"
          />
          <StatKarte
            value={stats?.products_with_recommendations ?? 0}
            label="Analysiert"
            icon={<ChartLineIcon />}
            tone="neutral"
          />
          <StatKarte
            value={`€${stats?.missed_revenue?.total?.toFixed(0) ?? '0'}`}
            label="Potenzial"
            icon={<ChartLineIcon />}
            tone="critical"
          />
        </InlineGrid>

        <PreisverlaufChart
          data={chartData}
          title="Preisentwicklung"
          subtitle="Letzte 30 Tage (erstes Produkt)"
        />

        {engineStatus && (
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">
                Preisanalyse-Engine
              </Text>
              <InlineStack gap="200">
                <Badge
                  tone={engineStatus.feature_flags ? 'success' : 'warning'}
                >
                  {engineStatus.feature_flags ? 'Aktiv' : 'Prüfen'}
                </Badge>
                <Text as="p">
                  Datenbasierte Preisanalyse v1.2
                </Text>
              </InlineStack>
            </BlockStack>
          </Card>
        )}

        {stats?.progress && (
          <FortschrittsCard progress={stats.progress} />
        )}
      </BlockStack>
    </Page>
  );
}
