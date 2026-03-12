'use client';

import { useQuery } from '@tanstack/react-query';
import { getDashboardStats, getEngineStatus } from '@/lib/api';
import {
  Page,
  Card,
  Text,
  Badge,
  Button,
  ProgressBar,
  List,
  BlockStack,
  InlineGrid,
  InlineStack,
  SkeletonPage,
} from '@shopify/polaris';

export default function AnalyticsPage() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });
  const { data: engineStatus } = useQuery({
    queryKey: ['engine-status'],
    queryFn: getEngineStatus,
  });

  if (isLoading) return <SkeletonPage />;

  return (
    <Page title="Analysen">
      <BlockStack gap="500">
        <Card>
          <BlockStack gap="400">
            <Text as="h2" variant="headingMd">
              Ungenutztes Potenzial
            </Text>
            <Text as="p" variant="headingXl" tone="critical">
              €{stats?.missed_revenue?.total?.toFixed(2) ?? '0.00'}
            </Text>
            <InlineGrid columns={{ xs: 1, sm: 3 }} gap="400">
              <BlockStack gap="100">
                <Text as="p" variant="headingLg">
                  {stats?.missed_revenue?.product_count ?? 0}
                </Text>
                <Text as="p" tone="subdued">
                  Betroffene Produkte
                </Text>
              </BlockStack>
              <BlockStack gap="100">
                <Text as="p" variant="headingLg">
                  €
                  {stats?.missed_revenue?.avg_per_product?.toFixed(2) ?? '0.00'}
                </Text>
                <Text as="p" tone="subdued">
                  Ø pro Produkt
                </Text>
              </BlockStack>
              <BlockStack gap="100">
                <Text as="p" variant="headingLg">
                  {stats?.missed_revenue?.recommendation_count ?? 0}
                </Text>
                <Text as="p" tone="subdued">
                  Ausstehende Empfehlungen
                </Text>
              </BlockStack>
            </InlineGrid>
            <Button url="/dashboard/products">Produkte optimieren →</Button>
          </BlockStack>
        </Card>

        <Card>
          <BlockStack gap="400">
            <Text as="h2" variant="headingMd">
              Empfehlungs-Übersicht
            </Text>
            <InlineGrid columns={{ xs: 1, sm: 3 }} gap="400">
              <BlockStack gap="100">
                <Text as="p" variant="headingLg">
                  {stats?.recommendations_pending ?? 0}
                </Text>
                <Text as="p" tone="subdued">
                  Ausstehend
                </Text>
              </BlockStack>
              <BlockStack gap="100">
                <Text as="p" variant="headingLg" tone="success">
                  {stats?.recommendations_applied ?? 0}
                </Text>
                <Text as="p" tone="subdued">
                  Angewendet
                </Text>
              </BlockStack>
              <BlockStack gap="100">
                <Text as="p" variant="headingLg">
                  {stats?.products_with_recommendations ?? 0}
                </Text>
                <Text as="p" tone="subdued">
                  Produkte mit Empfehlung
                </Text>
              </BlockStack>
            </InlineGrid>
          </BlockStack>
        </Card>

        {engineStatus && (
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">
                ML Pricing Engine
              </Text>
              <InlineStack gap="200">
                <Badge
                  tone={
                    engineStatus.feature_flags ? 'success' : 'warning'
                  }
                >
                  {engineStatus.feature_flags ? 'Aktiv' : 'Prüfen'}
                </Badge>
                <Text as="p">
                  Engine: XGBoost v1.2 + Meta-Labeler
                </Text>
              </InlineStack>
            </BlockStack>
          </Card>
        )}

        <Card>
          <BlockStack gap="400">
            <Text as="h2" variant="headingMd">
              Optimierungs-Fortschritt
            </Text>
            <Badge
              tone={
                stats?.progress.level === 'platinum'
                  ? 'success'
                  : stats?.progress.level === 'gold'
                    ? 'warning'
                    : stats?.progress.level === 'silver'
                      ? 'info'
                      : 'attention'
              }
            >
              {stats?.progress.level?.toUpperCase() ?? 'BRONZE'}
            </Badge>
            <ProgressBar
              progress={
                (stats?.progress.next_level_points ?? 100) > 0
                  ? ((stats?.progress.points ?? 0) /
                      (stats?.progress.next_level_points ?? 100)) *
                    100
                  : 0
              }
              size="small"
            />
            <Text as="p">
              {stats?.progress.points_needed ?? 0} Punkte bis nächstes Level
            </Text>
            <List type="bullet">
              {stats?.progress.pending_steps?.map((step) => (
                <List.Item key={step.text}>
                  {step.text} <Badge tone="info">{`+${step.points} Punkte`}</Badge>
                </List.Item>
              ))}
            </List>
          </BlockStack>
        </Card>
      </BlockStack>
    </Page>
  );
}
