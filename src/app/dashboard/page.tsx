'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import { getDashboardStats, getCurrentShop, syncProductsFromShopify } from '@/lib/api';
import {
  Page,
  Banner,
  BlockStack,
  InlineGrid,
  Layout,
} from '@shopify/polaris';
import { ProductIcon, AlertCircleIcon, CashEuroIcon, CheckCircleIcon } from '@shopify/polaris-icons';
import { StatKarte } from '@/components/StatKarte';
import { FortschrittsCard } from '@/components/FortschrittsCard';
import { QuickActionsCard } from '@/components/QuickActionsCard';

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return 'Morgen';
  if (h < 18) return 'Tag';
  return 'Abend';
}

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

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const suffix = useShopSuffix();

  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });
  const { data: shopData } = useQuery({
    queryKey: ['current-shop'],
    queryFn: getCurrentShop,
  });
  const syncMutation = useMutation({
    mutationFn: syncProductsFromShopify,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });

  const shopName = shopData?.shop?.name ?? shopData?.shop?.shop_url ?? 'dein Shop';
  const pendingCount = stats?.recommendations_pending ?? 0;
  const missedRevenue = stats?.missed_revenue?.total ?? 0;

  if (isLoading) {
    return (
      <Page title="Dashboard">
        <BlockStack gap="400">
          <div style={{ padding: 24, background: '#fff', borderRadius: 12 }}>
            Lade Dashboard...
          </div>
        </BlockStack>
      </Page>
    );
  }

  if (error || !stats) {
    return (
      <Page title="Dashboard">
        <Banner tone="critical" title="Fehler beim Laden">
          Dashboard konnte nicht geladen werden.
          {error instanceof Error && ` (${error.message})`}
        </Banner>
      </Page>
    );
  }

  const urgentStep = stats.next_steps?.find((s) => s.urgent);

  return (
    <Page
      title={`Guten ${getGreeting()}, ${shopName}! 👋`}
      subtitle="Hier ist dein aktueller Überblick"
    >
      <BlockStack gap="500">
        {urgentStep && pendingCount > 0 && (
          <Banner
            tone="warning"
            title={`${pendingCount} Preisempfehlungen warten`}
            action={{
              content: urgentStep.action,
              url: urgentStep.href + suffix,
            }}
          >
            Ungenutztes Potenzial: bis zu {Math.round(missedRevenue)}€ mehr
            Umsatz
          </Banner>
        )}

        <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="400">
          <StatKarte
            value={stats.products_count}
            label="Produkte synchronisiert"
            icon={<ProductIcon />}
            tone="neutral"
          />
          <StatKarte
            value={stats.recommendations_pending}
            label="Offene Empfehlungen"
            icon={<AlertCircleIcon />}
            tone="warning"
          />
          <StatKarte
            value={`€${stats.missed_revenue.total.toFixed(0)}`}
            label="Ungenutztes Potenzial"
            icon={<CashEuroIcon />}
            tone="critical"
          />
          <StatKarte
            value={stats.recommendations_applied}
            label="Empfehlungen umgesetzt"
            icon={<CheckCircleIcon />}
            tone="success"
          />
        </InlineGrid>

        <Layout>
          <Layout.Section>
            <FortschrittsCard progress={stats.progress} />
          </Layout.Section>
          <Layout.Section variant="oneThird">
            <QuickActionsCard
              pendingCount={pendingCount}
              onSync={() => syncMutation.mutate()}
              isSyncing={syncMutation.isPending}
              suffix={suffix}
            />
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}
