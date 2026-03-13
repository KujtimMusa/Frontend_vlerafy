'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { fetchProducts, getDashboardStats } from '@/lib/api';
import {
  Page,
  Card,
  Text,
  IndexTable,
  SkeletonPage,
  BlockStack,
  InlineGrid,
} from '@shopify/polaris';
import type { Product } from '@/types/models';

export default function ProductsPage() {
  const router = useRouter();
  const { data: products = [], isLoading } = useQuery({
    queryKey: ['products'],
    queryFn: () => fetchProducts(),
  });
  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });

  if (isLoading) return <SkeletonPage />;

  return (
    <Page title="Produkte">
      <BlockStack gap="500">
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
