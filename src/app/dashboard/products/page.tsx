'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { fetchProducts, getDashboardStats } from '@/lib/api';

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

  if (isLoading) return <s-skeleton-page />;

  return (
    <s-page title="Produkte">
      <s-layout variant="1-1-1-1">
        <s-card>
          <s-text variant="headingLg">
            {stats?.products_count ?? products.length}
          </s-text>
          <s-text>Gesamt</s-text>
        </s-card>
        <s-card>
          <s-text variant="headingLg">
            {stats?.products_with_recommendations ?? 0}
          </s-text>
          <s-text>Mit Empfehlung</s-text>
        </s-card>
        <s-card>
          <s-text variant="headingLg">
            {stats?.recommendations_pending ?? 0}
          </s-text>
          <s-text>Ausstehend</s-text>
        </s-card>
        <s-card>
          <s-text variant="headingLg">
            €{stats?.missed_revenue?.total?.toFixed(0) ?? '0'}
          </s-text>
          <s-text>Ungenutztes Potenzial</s-text>
        </s-card>
      </s-layout>

      <s-index-table>
        {products.map((product) => (
          <s-index-table-row
            key={product.id}
            onClick={() => router.push(`/dashboard/products/${product.id}`)}
          >
            <s-index-table-cell>{product.title}</s-index-table-cell>
            <s-index-table-cell>€{product.price}</s-index-table-cell>
            <s-index-table-cell>
              {product.inventory ?? 0} Stück
            </s-index-table-cell>
            <s-index-table-cell>
              <s-badge tone={product.is_demo ? 'info' : 'success'}>
                {product.is_demo ? 'Demo' : 'Live'}
              </s-badge>
            </s-index-table-cell>
          </s-index-table-row>
        ))}
      </s-index-table>
    </s-page>
  );
}
