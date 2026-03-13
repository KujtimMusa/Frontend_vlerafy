'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Page,
  Card,
  Text,
  BlockStack,
  InlineStack,
  Button,
  Layout,
  Divider,
  Badge,
} from '@shopify/polaris';
import { RefreshIcon } from '@shopify/polaris-icons';
import { getCurrentShop, syncProductsFromShopify } from '@/lib/api';

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '–';
  try {
    return new Date(iso).toLocaleDateString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  } catch {
    return '–';
  }
}

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { data: shopData, isLoading } = useQuery({
    queryKey: ['current-shop'],
    queryFn: getCurrentShop,
  });
  const syncMutation = useMutation({
    mutationFn: syncProductsFromShopify,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['current-shop'] });
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });

  const shop = shopData?.shop;
  const shopDomain = shop?.shop_url ?? (typeof window !== 'undefined' ? localStorage.getItem('shop_domain') : null) ?? '–';
  const shopId = shop?.id ?? (typeof window !== 'undefined' ? localStorage.getItem('current_shop_id') : null) ?? '–';
  const productCount = shop?.product_count ?? 0;
  const installedAt = shop?.shop_url ? null : undefined;

  if (isLoading) {
    return (
      <Page title="Einstellungen">
        <Card>
          <Text as="p">Lade Einstellungen...</Text>
        </Card>
      </Page>
    );
  }

  return (
    <Page title="Einstellungen">
      <Layout>
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">
                Shop-Informationen
              </Text>
              <Divider />
              {[
                ['Shop-URL', shopDomain],
                ['Shop-ID', String(shopId)],
                ['Verbunden seit', formatDate(installedAt)],
                ['Produkte synchronisiert', String(productCount)],
              ].map(([label, value]) => (
                <InlineStack key={String(label)} align="space-between">
                  <Text as="span" tone="subdued">{label}</Text>
                  <Text as="span" fontWeight="semibold">{value}</Text>
                </InlineStack>
              ))}
            </BlockStack>
          </Card>

          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">
                Produkt-Synchronisation
              </Text>
              <Text as="p" tone="subdued">
                Synchronisiere deine Shopify-Produkte für aktuelle
                Preisempfehlungen.
              </Text>
              <Button
                onClick={() => syncMutation.mutate()}
                loading={syncMutation.isPending}
                variant="primary"
                icon={RefreshIcon}
              >
                Jetzt synchronisieren
              </Button>
            </BlockStack>
          </Card>

          <Card>
            <BlockStack gap="300">
              <InlineStack gap="200" blockAlign="center">
                <div
                  style={{
                    width: 28,
                    height: 28,
                    background: 'linear-gradient(135deg, #4F46E5, #7C3AED)',
                    borderRadius: 6,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <span style={{ color: '#fff', fontSize: 13, fontWeight: 700 }}>
                    v
                  </span>
                </div>
                <Text as="h2" variant="headingMd">Über vlerafy</Text>
              </InlineStack>
              <Text as="p" tone="subdued">
                vlerafy analysiert deine Produktpreise automatisch und schlägt
                datenbasierte Optimierungen vor – damit du immer den richtigen
                Preis zur richtigen Zeit hast.
              </Text>
              <InlineStack align="space-between">
                <Text as="span" tone="subdued">Version</Text>
                <Badge>1.0</Badge>
              </InlineStack>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
