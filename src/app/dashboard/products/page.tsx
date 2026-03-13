'use client';

import { useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { fetchProducts, getDashboardStats, syncProductsFromShopify } from '@/lib/api';
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
} from '@shopify/polaris';
import type { Product } from '@/types/models';

export default function ProductsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
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

  // Auto-Sync wenn 0 Produkte und Shop verbunden (z.B. OAuth-Sync war fehlgeschlagen)
  useEffect(() => {
    if (
      !isLoading &&
      products.length === 0 &&
      !autoSyncDone.current &&
      (typeof window !== 'undefined' &&
        (localStorage.getItem('shop_domain') || localStorage.getItem('current_shop_id')))
    ) {
      autoSyncDone.current = true;
      syncMutation.mutate();
    }
  }, [isLoading, products.length]);

  if (isLoading) return <SkeletonPage />;

  const showDebug = typeof window !== 'undefined' && window.location.search.includes('debug=1');

  return (
    <Page title="Produkte">
      <BlockStack gap="500">
        {showDebug && (
          <Banner tone="info" title="Debug-Modus">
            <Text as="p">
              URL: ?shop={typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('shop') || '(fehlt)' : '-'} |
              localStorage shop_domain: {typeof window !== 'undefined' ? localStorage.getItem('shop_domain') || '(fehlt)' : '-'} |
              Produkte: {products.length} |
              Siehe Konsole für [API DEBUG]
            </Text>
          </Banner>
        )}
        {syncMutation.isPending && (
          <Banner tone="info">Produkte werden von deinem Shopify-Shop synchronisiert...</Banner>
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
        {products.length === 0 && !syncMutation.isPending && (
          <Banner tone="warning">
            <BlockStack gap="200">
              <Text as="p">Noch keine Produkte. Synchronisiere sie jetzt aus deinem Shopify-Shop.</Text>
              <Button onClick={() => syncMutation.mutate()} loading={syncMutation.isPending}>
                Produkte synchronisieren
              </Button>
            </BlockStack>
          </Banner>
        )}
        <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="400">
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingLg">
                {stats?.products_count ?? products.length}
              </Text>
              <Text as="p">Gesamt</Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingLg">
                {stats?.products_with_recommendations ?? 0}
              </Text>
              <Text as="p">Mit Empfehlung</Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingLg">
                {stats?.recommendations_pending ?? 0}
              </Text>
              <Text as="p">Ausstehend</Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingLg">
                €{stats?.missed_revenue?.total?.toFixed(0) ?? '0'}
              </Text>
              <Text as="p">Ungenutztes Potenzial</Text>
            </BlockStack>
          </Card>
        </InlineGrid>

        <Card>
          <IndexTable
            resourceName={{ singular: 'Produkt', plural: 'Produkte' }}
            headings={[
              { title: 'Produkt' },
              { title: 'Preis' },
              { title: 'Lager' },
            ]}
            itemCount={products.length}
            selectable={false}
          >
            {products.map((product: Product, index: number) => (
              <IndexTable.Row
                key={product.id}
                id={String(product.id)}
                position={index}
                onClick={() =>
                  router.push(`/dashboard/products/${product.id}`)
                }
              >
                <IndexTable.Cell>
                  <Text as="span" fontWeight="semibold">
                    {product.title}
                  </Text>
                </IndexTable.Cell>
                <IndexTable.Cell>€{product.price}</IndexTable.Cell>
                <IndexTable.Cell>
                  {product.inventory ?? 0} Stück
                </IndexTable.Cell>
              </IndexTable.Row>
            ))}
          </IndexTable>
        </Card>
      </BlockStack>
    </Page>
  );
}
