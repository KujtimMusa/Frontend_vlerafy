'use client';

import { useQuery } from '@tanstack/react-query';
import { getDashboardStats } from '@/lib/api';
import {
  Page,
  Card,
  Text,
  Badge,
  Banner,
  Button,
  ProgressBar,
  List,
  Layout,
  BlockStack,
  InlineGrid,
} from '@shopify/polaris';

export default function DashboardPage() {
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });

  if (isLoading)
    return (
      <Page title="Dashboard">
        <Card>
          <Text as="p">Lade Dashboard...</Text>
        </Card>
      </Page>
    );
  if (error || !stats)
    return (
      <Page title="Dashboard">
        <Banner tone="critical" title="Fehler beim Laden">
          Dashboard konnte nicht geladen werden.
          {error instanceof Error && ` (${error.message})`}
        </Banner>
      </Page>
    );

  const nextLevel =
    stats.progress.level === 'bronze'
      ? 'Silver'
      : stats.progress.level === 'silver'
        ? 'Gold'
        : stats.progress.level === 'gold'
          ? 'Platinum'
          : '🏆 Max';

  const urgentStep = stats.next_steps?.find((s) => s.urgent);

  return (
    <Page title="Dashboard">
      <BlockStack gap="500">
        {urgentStep && (
          <Banner tone="warning" title={urgentStep.title}>
            <BlockStack gap="300">
              <Text as="p">{urgentStep.description}</Text>
              <Button url={urgentStep.href}>{urgentStep.action}</Button>
            </BlockStack>
          </Banner>
        )}

        <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="400">
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingLg">
                {stats.products_count}
              </Text>
              <Text as="p">Produkte</Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingLg">
                {stats.recommendations_pending}
              </Text>
              <Text as="p">Offene Empfehlungen</Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingLg" tone="critical">
                €{stats.missed_revenue.total.toFixed(2)}
              </Text>
              <Text as="p">Ungenutztes Potenzial</Text>
            </BlockStack>
          </Card>
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingLg" tone="success">
                {stats.recommendations_applied}
              </Text>
              <Text as="p">Empfehlungen angewendet</Text>
            </BlockStack>
          </Card>
        </InlineGrid>

        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">
                  Dein Fortschritt
                </Text>
                <Badge
                  tone={
                    stats.progress.level === 'platinum'
                      ? 'success'
                      : stats.progress.level === 'gold'
                        ? 'warning'
                        : stats.progress.level === 'silver'
                          ? 'info'
                          : 'attention'
                  }
                >
                  {stats.progress.level.toUpperCase()}
                </Badge>
                <ProgressBar
                  progress={
                    stats.progress.next_level_points > 0
                      ? (stats.progress.points / stats.progress.next_level_points) *
                        100
                      : 0
                  }
                  size="small"
                />
                <Text as="p">
                  {stats.progress.points}/{stats.progress.next_level_points}{' '}
                  Punkte bis {nextLevel}
                </Text>
                <List type="bullet">
                  {stats.progress.completed_steps.map((step) => (
                    <List.Item key={step}>✓ {step}</List.Item>
                  ))}
                  {stats.progress.pending_steps.map((step) => (
                    <List.Item key={step.text}>
                      ○ {step.text}{' '}
                      <Badge tone="info">{`+${step.points} Punkte`}</Badge>
                    </List.Item>
                  ))}
                </List>
              </BlockStack>
            </Card>
          </Layout.Section>
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">
                  Nächste Schritte
                </Text>
                <BlockStack gap="200">
                  {stats.next_steps?.map((step) => (
                    <Button
                      key={step.title}
                      url={step.href}
                      variant="plain"
                      removeUnderline
                    >
                      {step.title} →
                    </Button>
                  ))}
                </BlockStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}
