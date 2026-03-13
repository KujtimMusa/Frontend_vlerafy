'use client';

import { Card, BlockStack, Text, Button } from '@shopify/polaris';
import { PriceListIcon, RefreshIcon, ChartLineIcon } from '@shopify/polaris-icons';

interface QuickActionsCardProps {
  pendingCount: number;
  onSync: () => void;
  isSyncing: boolean;
  suffix: string;
}

export function QuickActionsCard({
  pendingCount,
  onSync,
  isSyncing,
  suffix,
}: QuickActionsCardProps) {
  return (
    <Card>
      <BlockStack gap="400">
        <Text as="h2" variant="headingMd">
          Schnellaktionen
        </Text>
        <Button
          variant="primary"
          url={`/dashboard/pricing${suffix}`}
          fullWidth
          icon={PriceListIcon}
        >
          {`${pendingCount} Preise optimieren`}
        </Button>
        <Button
          variant="secondary"
          onClick={onSync}
          loading={isSyncing}
          fullWidth
          icon={RefreshIcon}
        >
          Produkte synchronisieren
        </Button>
        <Button
          variant="plain"
          url={`/dashboard/analytics${suffix}`}
          fullWidth
          icon={ChartLineIcon}
        >
          Analysen anzeigen
        </Button>
      </BlockStack>
    </Card>
  );
}
