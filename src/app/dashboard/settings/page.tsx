'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import { getCurrentShop, syncProductsFromShopify } from '@/lib/api';

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
  void useShopSuffix(); // kept for future link suffix
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
      <div className="vlerafy-main">
        <s-page title="Einstellungen" />
        <s-section>
          <s-stack direction="block" gap="4">
            <s-paragraph tone="subdued">Lade Einstellungen...</s-paragraph>
          </s-stack>
        </s-section>
      </div>
    );
  }

  return (
    <div className="vlerafy-main">
      <s-page title="Einstellungen" />
      <div className="vlerafy-page-header">
        <h1 className="vlerafy-page-title">Einstellungen</h1>
        <p className="vlerafy-page-subtitle">Shop-Verbindung und Synchronisation</p>
      </div>
      <s-grid columns="1" gap="4">
        <s-section>
          <s-stack direction="block" gap="4">
            <s-heading size="md">Shop-Informationen</s-heading>
            <s-divider />
            {[
              ['Shop-URL', shopDomain],
              ['Shop-ID', String(shopId)],
              ['Verbunden seit', formatDate(installedAt)],
              ['Produkte synchronisiert', String(productCount)],
            ].map(([label, value]) => (
              <s-stack key={String(label)} direction="inline" gap="2" style={{ justifyContent: 'space-between' }}>
                <s-paragraph tone="subdued">{label}</s-paragraph>
                <s-text font-weight="semibold">{value}</s-text>
              </s-stack>
            ))}
          </s-stack>
        </s-section>

        <s-section>
          <s-stack direction="block" gap="4">
            <s-heading size="md">Produkt-Synchronisation</s-heading>
            <s-paragraph tone="subdued">
              Synchronisiere deine Shopify-Produkte für aktuelle Preisempfehlungen.
            </s-paragraph>
            <s-button
              variant="primary"
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              loading={syncMutation.isPending ? 'true' : undefined}
            >
              Jetzt synchronisieren
            </s-button>
          </s-stack>
        </s-section>

        <s-section>
          <s-stack direction="block" gap="3">
            <s-stack direction="inline" gap="2" style={{ alignItems: 'center' }}>
              <div
                className="vlerafy-empty-state-icon"
                style={{ width: 28, height: 28, margin: 0 }}
              >
                <span style={{ color: 'var(--v-navy-700)', fontSize: 13, fontWeight: 700 }}>v</span>
              </div>
              <s-heading size="md">Über vlerafy</s-heading>
            </s-stack>
            <s-paragraph tone="subdued">
              vlerafy analysiert deine Produktpreise automatisch und schlägt datenbasierte
              Optimierungen vor – damit du immer den richtigen Preis zur richtigen Zeit hast.
            </s-paragraph>
            <s-stack direction="inline" gap="2" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
              <s-paragraph tone="subdued">Version</s-paragraph>
              <s-badge>1.0</s-badge>
            </s-stack>
          </s-stack>
        </s-section>
      </s-grid>
    </div>
  );
}
