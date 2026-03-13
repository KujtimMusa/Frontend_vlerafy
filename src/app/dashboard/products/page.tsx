'use client';

import { useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  fetchProducts,
  getDashboardStats,
  syncProductsFromShopify,
} from '@/lib/api';
import {
  Page,
  Card,
  Text,
  IndexTable,
  SkeletonPage,
  BlockStack,
  InlineGrid,
  Banner,
  Button,
  EmptyState,
} from '@shopify/polaris';
import { ProductIcon, AlertCircleIcon, CashEuroIcon } from '@shopify/polaris-icons';
import { StatKarte } from '@/components/StatKarte';
import type { Product } from '@/types/models';

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

function formatPrice(v: number): string {
  return new Intl.NumberFormat('de-DE', {
    style: 'currency',
    currency: 'EUR',
  }).format(v);
}

export default function ProductsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const suffix = useShopSuffix();
  const autoSyncDone = useRef(false);

  const { data: products = [], isLoading } = useQuery({
    queryKey: ['products'],
    queryFn: () => fetchProducts(),
  });
  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });
  const syncMutation = useMutation({
    mutationFn: syncProductsFromShopify,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
    },
  });

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

  if (isLoading) {
    return (
      <SkeletonPage primaryAction>
        <BlockStack gap="400">
          <Card>
            <BlockStack gap="300">
              <div style={{ height: 60 }} />
              <div style={{ height: 200 }} />
            </BlockStack>
          </Card>
        </BlockStack>
      </SkeletonPage>
    );
  }

  return (
    <Page
      title="Produkte"
      primaryAction={{
        content: 'Synchronisieren',
        onAction: handleSync,
        loading: syncMutation.isPending,
        icon: ProductIcon,
      }}
      secondaryActions={[
        {
          content: 'Alle analysieren',
          url: `/dashboard/pricing${suffix}`,
        },
      ]}
    >
      <BlockStack gap="500">
        {syncMutation.isPending && (
          <Banner tone="info">
            Produkte werden von deinem Shopify-Shop synchronisiert...
          </Banner>
        )}
        {syncMutation.isError && (
          <Banner
            tone="critical"
            onDismiss={() => syncMutation.reset()}
            action={{
              content: 'Erneut versuchen',
              onAction: () => syncMutation.mutate(),
            }}
          >
            Sync fehlgeschlagen. Bitte erneut versuchen.
          </Banner>
        )}

        {products.length === 0 && !syncMutation.isPending ? (
          <EmptyState
            heading="Noch keine Produkte geladen"
            action={{
              content: 'Produkte synchronisieren',
              onAction: handleSync,
              loading: syncMutation.isPending,
            }}
            image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
          >
            Verbinde deinen Shopify-Shop um smarte Preisempfehlungen zu
            erhalten.
          </EmptyState>
        ) : (
          <>
            <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="400">
              <StatKarte
                value={stats?.products_count ?? products.length}
                label="Gesamt"
                icon={<ProductIcon />}
                tone="neutral"
              />
              <StatKarte
                value={stats?.products_with_recommendations ?? 0}
                label="Mit Empfehlung"
                icon={<AlertCircleIcon />}
                tone="neutral"
              />
              <StatKarte
                value={stats?.recommendations_pending ?? 0}
                label="Ausstehend"
                icon={<AlertCircleIcon />}
                tone="warning"
              />
              <StatKarte
                value={`€${stats?.missed_revenue?.total?.toFixed(0) ?? '0'}`}
                label="Ungenutztes Potenzial"
                icon={<CashEuroIcon />}
                tone="critical"
              />
            </InlineGrid>

            <Card>
              <IndexTable
                resourceName={{ singular: 'Produkt', plural: 'Produkte' }}
                headings={[
                  { title: 'Produkt' },
                  { title: 'Preis' },
                  { title: 'Lager' },
                  { title: 'Aktion' },
                ]}
                itemCount={products.length}
                selectable={false}
              >
                {products.map((product: Product, index: number) => (
                  <ProductRow
                    key={product.id}
                    product={product}
                    index={index}
                    router={router}
                    suffix={suffix}
                  />
                ))}
              </IndexTable>
            </Card>
          </>
        )}
      </BlockStack>
    </Page>
  );
}

function ProductRow({
  product,
  index,
  router,
  suffix,
}: {
  product: Product;
  index: number;
  router: ReturnType<typeof useRouter>;
  suffix: string;
}) {
  const inv = product.inventory ?? 0;
  const invTone = inv === 0 ? 'critical' : inv < 5 ? 'caution' : undefined;

  return (
    <IndexTable.Row
      id={String(product.id)}
      position={index}
      onClick={() => router.push(`/dashboard/products/${product.id}${suffix}`)}
    >
      <IndexTable.Cell>
        <Text as="span" fontWeight="semibold">
          {product.title}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>{formatPrice(product.price)}</IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" tone={invTone}>
          {inv} Stück
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Button
          variant="plain"
          size="slim"
          url={`/dashboard/products/${product.id}${suffix}`}
        >
          Ansehen
        </Button>
      </IndexTable.Cell>
    </IndexTable.Row>
  );
}
