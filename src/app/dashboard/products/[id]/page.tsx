'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useSearchParams } from 'next/navigation';
import { useState, useEffect } from 'react';
import {
  fetchProducts,
  getRecommendation,
  generateRecommendation,
  getMarginHistory,
  getCompetitorAnalysis,
  searchCompetitors,
  getProductCosts,
  saveProductCosts,
  calculateMargin,
  applyPrice,
  markRecommendationApplied,
  getCategoryDefaults,
} from '@/lib/api';
import { showToast } from '@/lib/toast';
import type { Recommendation } from '@/types/models';
import {
  Page,
  Card,
  Text,
  Badge,
  Banner,
  Button,
  ProgressBar,
  List,
  BlockStack,
  InlineStack,
  InlineGrid,
  IndexTable,
  Select,
  TextField,
  SkeletonPage,
  SkeletonBodyText,
  Layout,
} from '@shopify/polaris';
import { PreisverlaufChart } from '@/components/PreisverlaufChart';

const PAYMENT_PROVIDERS = [
  { label: 'Stripe (2.9% + 0.30€)', value: 'stripe' },
  { label: 'PayPal (2.49% + 0.35€)', value: 'paypal' },
  { label: 'Klarna (4.5%)', value: 'klarna' },
  { label: 'Custom', value: 'custom' },
];

const CATEGORIES = [
  { label: 'Fashion', value: 'fashion' },
  { label: 'Electronics', value: 'electronics' },
  { label: 'Beauty', value: 'beauty' },
  { label: 'Home', value: 'home' },
  { label: 'Food', value: 'food' },
];

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

export default function ProductDetailPage() {
  const { id } = useParams();
  const productId = Number(id);
  const qc = useQueryClient();
  const suffix = useShopSuffix();

  const [costForm, setCostForm] = useState({
    purchase_cost: '',
    shipping_cost: '',
    packaging_cost: '',
    payment_provider: 'stripe',
    payment_fee_percentage: '2.9',
    payment_fee_fixed: '0.30',
    country_code: 'DE',
    category: 'fashion',
  });
  const [showCostForm, setShowCostForm] = useState(false);
  const [strategyDetailsOpen, setStrategyDetailsOpen] = useState(false);

  const { data: products = [] } = useQuery({
    queryKey: ['products'],
    queryFn: () => fetchProducts(),
  });
  const product = products.find((p) => p.id === productId);

  const { data: recommendation, isLoading: recLoading } = useQuery<
    Recommendation | null
  >({
    queryKey: ['recommendation', productId],
    queryFn: () => getRecommendation(productId),
    enabled: !!productId,
  });

  const { data: competitors, isLoading: compLoading } = useQuery({
    queryKey: ['competitors', productId],
    queryFn: () => getCompetitorAnalysis(productId),
    enabled: !!productId,
  });

  const { data: existingCosts } = useQuery({
    queryKey: ['costs', product?.shopify_product_id],
    queryFn: () => getProductCosts(product?.shopify_product_id ?? ''),
    enabled: !!product?.shopify_product_id,
  });

  useEffect(() => {
    if (existingCosts) {
      setCostForm({
        purchase_cost: String(existingCosts.purchase_cost),
        shipping_cost: String(existingCosts.shipping_cost),
        packaging_cost: String(existingCosts.packaging_cost),
        payment_provider: existingCosts.payment_provider,
        payment_fee_percentage: String(existingCosts.payment_fee_percentage),
        payment_fee_fixed: String(existingCosts.payment_fee_fixed),
        country_code: existingCosts.country_code,
        category: existingCosts.category ?? 'fashion',
      });
    }
  }, [existingCosts]);

  const { data: marginHistory } = useQuery({
    queryKey: ['margin-history', product?.shopify_product_id],
    queryFn: () => getMarginHistory(product!.shopify_product_id, 30),
    enabled: !!product?.shopify_product_id,
  });
  const chartData =
    marginHistory?.history?.map((h) => ({
      date: new Date(h.date).toLocaleDateString('de-DE', {
        day: '2-digit',
        month: '2-digit',
      }),
      price: h.selling_price,
    })) ?? [];

  const { data: margin } = useQuery({
    queryKey: [
      'margin',
      product?.shopify_product_id,
      recommendation?.recommended_price ?? product?.price,
    ],
    queryFn: () =>
      calculateMargin(
        product!.shopify_product_id,
        recommendation?.recommended_price ?? product!.price ?? 0
      ),
    enabled: !!existingCosts && !!product?.shopify_product_id,
  });

  const generateMutation = useMutation({
    mutationFn: () => generateRecommendation(productId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recommendation', productId] });
      showToast('Empfehlung generiert!', { duration: 3000 });
    },
    onError: () => showToast('Fehler beim Generieren', { isError: true }),
  });

  const applyMutation = useMutation({
    mutationFn: async () => {
      if (!recommendation) throw new Error('Keine Empfehlung');
      await applyPrice(productId, recommendation.recommended_price);
      await markRecommendationApplied(recommendation.id);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['products'] });
      qc.invalidateQueries({ queryKey: ['dashboard-stats'] });
      showToast('Preis erfolgreich übernommen!', { duration: 3000 });
    },
    onError: () => showToast('Fehler beim Übernehmen', { isError: true }),
  });

  const saveCostsMutation = useMutation({
    mutationFn: () =>
      saveProductCosts({
        product_id: product!.shopify_product_id,
        purchase_cost: parseFloat(costForm.purchase_cost),
        shipping_cost: parseFloat(costForm.shipping_cost),
        packaging_cost: parseFloat(costForm.packaging_cost),
        payment_provider: costForm.payment_provider,
        payment_fee_percentage: parseFloat(costForm.payment_fee_percentage),
        payment_fee_fixed: parseFloat(costForm.payment_fee_fixed),
        country_code: costForm.country_code,
        category: costForm.category,
      }),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ['costs', product?.shopify_product_id],
      });
      qc.invalidateQueries({ queryKey: ['margin'] });
      setShowCostForm(false);
      showToast('Kostendaten gespeichert!', { duration: 3000 });
    },
    onError: () => showToast('Fehler beim Speichern', { isError: true }),
  });

  const competitorSearchMutation = useMutation({
    mutationFn: () => searchCompetitors(productId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['competitors', productId] });
      showToast('Wettbewerber aktualisiert!', { duration: 3000 });
    },
    onError: () =>
      showToast('Competitor Search fehlgeschlagen', { isError: true }),
  });

  const loadCategoryDefaults = async (category: string) => {
    const defaults = await getCategoryDefaults(category);
    setCostForm((prev) => ({
      ...prev,
      category,
      shipping_cost: String(defaults.shipping_estimate),
      packaging_cost: String(defaults.packaging_estimate),
    }));
  };

  if (!product) return <SkeletonPage />;

  const raw =
    typeof recommendation?.reasoning === 'object'
      ? (recommendation.reasoning as Record<string, unknown>)?.summary ??
        JSON.stringify(recommendation.reasoning)
      : recommendation?.reasoning ?? '';
  const reasoningText = typeof raw === 'string' ? raw : JSON.stringify(raw);

  const confidencePct = recommendation
    ? Math.round(recommendation.confidence * 100)
    : 0;
  const mlConfidencePct = recommendation?.ml_confidence
    ? Math.round(recommendation.ml_confidence * 100)
    : null;
  const metaConfidencePct = recommendation?.meta_labeler_confidence
    ? Math.round(recommendation.meta_labeler_confidence * 100)
    : null;

  const compList = competitors?.competitors ?? [];
  const compDisplay = compList.map(
    (c: {
      title?: string;
      competitor_name?: string;
      price: number;
      url?: string;
      source?: string;
      competitor_url?: string;
    }) => ({
      title: c.title ?? c.competitor_name ?? 'Unbekannt',
      price: c.price,
      source: c.source ?? c.competitor_name ?? '–',
      url: c.url ?? c.competitor_url ?? '',
    })
  );

  return (
    <Page
      title={product.title}
      backAction={{ content: 'Produkte', url: `/dashboard/products${suffix}` }}
    >
      <Layout>
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">
                Preisempfehlung
              </Text>
              {recLoading ? (
                <SkeletonBodyText />
              ) : recommendation ? (
                <>
                  <InlineGrid columns={{ xs: 1, sm: 2 }} gap="400">
                    <BlockStack gap="100">
                      <Text as="p" tone="subdued">
                        Aktueller Preis
                      </Text>
                      <Text as="p" variant="headingXl">
                        €{product.price}
                      </Text>
                    </BlockStack>
                    <BlockStack gap="100">
                      <Badge tone="info">{recommendation.strategy}</Badge>
                      <Text as="p" tone="subdued">
                        Empfohlener Preis
                      </Text>
                      <Text as="p" variant="headingXl">
                        €{recommendation.recommended_price}
                      </Text>
                      <Text
                        as="p"
                        tone={
                          recommendation.price_change_pct >= 0
                            ? 'success'
                            : 'critical'
                        }
                      >
                        {recommendation.price_change_pct >= 0 ? '+' : ''}
                        {recommendation.price_change_pct.toFixed(1)}%
                      </Text>
                    </BlockStack>
                  </InlineGrid>

                  <Text as="h3" variant="headingMd">
                    Analyse-Sicherheit
                  </Text>
                  <InlineGrid columns={{ xs: 1, sm: 3 }} gap="400">
                    <BlockStack gap="100">
                      <Text as="p" tone="subdued">
                        Gesamt
                      </Text>
                      <Badge
                        tone={
                          confidencePct >= 80
                            ? 'success'
                            : confidencePct >= 60
                              ? 'warning'
                              : 'critical'
                        }
                      >
                        {`${confidencePct}% ${recommendation.confidence_label ?? ''}`}
                      </Badge>
                    </BlockStack>
                    {mlConfidencePct != null && (
                      <BlockStack gap="100">
                        <Text as="p" tone="subdued">
                          Kernanalyse
                        </Text>
                        <Badge
                          tone={mlConfidencePct >= 80 ? 'success' : 'warning'}
                        >
                          {`${mlConfidencePct}%`}
                        </Badge>
                      </BlockStack>
                    )}
                    {metaConfidencePct != null && (
                      <BlockStack gap="100">
                        <Text as="p" tone="subdued">
                          Qualitätsprüfung
                        </Text>
                        <Badge
                          tone={
                            recommendation.meta_labeler_approved
                              ? 'success'
                              : 'warning'
                          }
                        >
                          {`${metaConfidencePct}% ${recommendation.meta_labeler_approved ? '✓' : '✗'}`}
                        </Badge>
                      </BlockStack>
                    )}
                  </InlineGrid>

                  {recommendation.competitor_avg_price != null && (
                    <InlineGrid columns={{ xs: 1, sm: 3 }} gap="400">
                      <BlockStack gap="100">
                        <Text as="p" tone="subdued">
                          Nachfragewachstum
                        </Text>
                        <Text as="p">
                          {recommendation.demand_growth != null
                            ? `${(recommendation.demand_growth * 100).toFixed(1)}%`
                            : '–'}
                        </Text>
                      </BlockStack>
                      <BlockStack gap="100">
                        <Text as="p" tone="subdued">
                          Tage Lagerbestand
                        </Text>
                        <Text as="p">
                          {recommendation.days_of_stock?.toFixed(0) ?? '–'}
                        </Text>
                      </BlockStack>
                      <BlockStack gap="100">
                        <Text as="p" tone="subdued">
                          Wettbewerber Ø
                        </Text>
                        <Text as="p">
                          €{recommendation.competitor_avg_price.toFixed(2)}
                        </Text>
                      </BlockStack>
                    </InlineGrid>
                  )}

                  {recommendation.strategy_details &&
                    recommendation.strategy_details.length > 0 && (
                      <BlockStack gap="200">
                        <Button
                          onClick={() =>
                            setStrategyDetailsOpen(!strategyDetailsOpen)
                          }
                          variant="plain"
                        >
                          {strategyDetailsOpen
                            ? 'Strategie Details ausblenden'
                            : 'Strategie Details anzeigen'}
                        </Button>
                        {strategyDetailsOpen && (
                          <BlockStack gap="200">
                            {recommendation.strategy_details.map(
                              (detail, i) => (
                                <Card key={i}>
                                  <BlockStack gap="200">
                                    <Badge>{detail.strategy}</Badge>
                                    <Text as="p">
                                      €{detail.recommended_price} –{' '}
                                      {detail.reasoning}
                                    </Text>
                                  </BlockStack>
                                </Card>
                              )
                            )}
                          </BlockStack>
                        )}
                      </BlockStack>
                    )}

                  <Text as="h3" variant="headingMd">
                    Begründung
                  </Text>
                  <Text as="p">{reasoningText}</Text>

                  <InlineStack gap="300">
                    <Button
                      variant="primary"
                      onClick={() => applyMutation.mutate()}
                      loading={applyMutation.isPending}
                    >
                      {`Preis übernehmen (€${recommendation.recommended_price})`}
                    </Button>
                    <Button
                      onClick={() => generateMutation.mutate()}
                      loading={generateMutation.isPending}
                    >
                      Neu generieren
                    </Button>
                  </InlineStack>
                </>
              ) : (
                <BlockStack gap="400">
                  <Text as="p" tone="subdued">
                    Noch keine Empfehlung für dieses Produkt.
                  </Text>
                  <Button
                    variant="primary"
                    onClick={() => generateMutation.mutate()}
                    loading={generateMutation.isPending}
                  >
                    Empfehlung generieren
                  </Button>
                </BlockStack>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        <Layout.Section>
          <PreisverlaufChart
            data={chartData}
            title="Preisentwicklung"
            subtitle="Letzte 30 Tage"
          />
        </Layout.Section>

        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">
                Margen-Analyse
              </Text>
              {margin?.has_cost_data ? (
                <>
                  <InlineGrid columns={{ xs: 1, sm: 2 }} gap="400">
                    <BlockStack gap="100">
                      <Text as="p" tone="subdued">
                        Verkaufspreis
                      </Text>
                      <Text as="p" variant="headingLg">
                        €{margin.selling_price}
                      </Text>
                    </BlockStack>
                    <BlockStack gap="100">
                      <Text as="p" tone="subdued">
                        Nettoerlös
                      </Text>
                      <Text as="p" variant="headingLg">
                        €{margin.net_revenue.toFixed(2)}
                      </Text>
                    </BlockStack>
                  </InlineGrid>

                  <Text as="h3" variant="headingMd">
                    Kostenaufstellung
                  </Text>
                  <List type="bullet">
                    <List.Item>
                      Einkauf: €{margin.costs.purchase.toFixed(2)}
                    </List.Item>
                    <List.Item>
                      Versand: €{margin.costs.shipping.toFixed(2)}
                    </List.Item>
                    <List.Item>
                      Verpackung: €{margin.costs.packaging.toFixed(2)}
                    </List.Item>
                    <List.Item>
                      Zahlungsgebühr ({margin.payment_provider}): €
                      {margin.costs.payment_fee.toFixed(2)}
                    </List.Item>
                    <List.Item>
                      <strong>
                        Gesamt: €{margin.costs.total_variable.toFixed(2)}
                      </strong>
                    </List.Item>
                  </List>

                  <Text as="p" variant="headingMd">
                    Deckungsbeitrag: €{margin.margin.euro.toFixed(2)} (
                    {margin.margin.percent.toFixed(1)}%)
                  </Text>
                  <ProgressBar
                    progress={margin.margin.percent}
                    size="small"
                  />

                  <Text as="h3" variant="headingMd">
                    Preis-Benchmarks
                  </Text>
                  <List type="bullet">
                    <List.Item>
                      Break-Even: €{margin.break_even_price.toFixed(2)}{' '}
                      <Badge
                        tone={
                          margin.is_above_break_even ? 'success' : 'critical'
                        }
                      >
                        {margin.is_above_break_even ? '✓ OK' : '✗ Unter Break-Even'}
                      </Badge>
                    </List.Item>
                    <List.Item>
                      Mindestpreis (20% Marge): €
                      {margin.recommended_min_price.toFixed(2)}{' '}
                      <Badge
                        tone={
                          margin.is_above_min_margin ? 'success' : 'warning'
                        }
                      >
                        {margin.is_above_min_margin ? '✓ OK' : '⚠ Unter Mindestmarge'}
                      </Badge>
                    </List.Item>
                    <List.Item>
                      MwSt: {margin.vat_rate}% ({margin.country_code})
                    </List.Item>
                  </List>

                  <Button onClick={() => setShowCostForm(true)}>
                    Kosten bearbeiten
                  </Button>
                </>
              ) : (
                <Banner tone="info" title="Keine Kostendaten">
                  Füge Kostendaten hinzu um die Marge zu berechnen.
                </Banner>
              )}

              {(showCostForm || !margin?.has_cost_data) && (
                <Card>
                  <BlockStack gap="400">
                    <Text as="h3" variant="headingMd">
                      Kostendaten eingeben
                    </Text>
                    <Select
                      label="Kategorie (lädt Standardwerte)"
                      options={CATEGORIES}
                      value={costForm.category}
                      onChange={(v) => loadCategoryDefaults(v || 'fashion')}
                    />
                    <TextField
                      label="Einkaufspreis (€)"
                      type="number"
                      value={costForm.purchase_cost}
                      onChange={(v) =>
                        setCostForm((p) => ({ ...p, purchase_cost: v }))
                      }
                      autoComplete="off"
                    />
                    <TextField
                      label="Versandkosten (€)"
                      type="number"
                      value={costForm.shipping_cost}
                      onChange={(v) =>
                        setCostForm((p) => ({ ...p, shipping_cost: v }))
                      }
                      autoComplete="off"
                    />
                    <TextField
                      label="Verpackungskosten (€)"
                      type="number"
                      value={costForm.packaging_cost}
                      onChange={(v) =>
                        setCostForm((p) => ({ ...p, packaging_cost: v }))
                      }
                      autoComplete="off"
                    />
                    <Select
                      label="Zahlungsanbieter"
                      options={PAYMENT_PROVIDERS}
                      value={costForm.payment_provider}
                      onChange={(v) =>
                        setCostForm((p) => ({
                          ...p,
                          payment_provider: v || 'stripe',
                        }))
                      }
                    />
                    <InlineStack gap="300">
                      <Button
                        variant="primary"
                        onClick={() => saveCostsMutation.mutate()}
                        loading={saveCostsMutation.isPending}
                      >
                        Speichern & Marge berechnen
                      </Button>
                      {showCostForm && (
                        <Button onClick={() => setShowCostForm(false)}>
                          Abbrechen
                        </Button>
                      )}
                    </InlineStack>
                  </BlockStack>
                </Card>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">
                Wettbewerbsanalyse
              </Text>
              {compLoading ? (
                <SkeletonBodyText />
              ) : competitors?.has_data ? (
                <>
                  <InlineGrid columns={{ xs: 1, sm: 3 }} gap="400">
                    <BlockStack gap="100">
                      <Text as="p" tone="subdued">
                        Dein Preis
                      </Text>
                      <Text as="p" variant="headingLg">
                        €{competitors.current_price}
                      </Text>
                    </BlockStack>
                    <BlockStack gap="100">
                      <Text as="p" tone="subdued">
                        Marktdurchschnitt
                      </Text>
                      <Text as="p" variant="headingLg">
                        €{competitors.competitor_avg?.toFixed(2)}
                      </Text>
                      <Text as="p" tone="subdued">
                        {competitors.competitor_count} Anbieter
                      </Text>
                    </BlockStack>
                    <BlockStack gap="100">
                      <Text as="p" tone="subdued">
                        Preisspanne
                      </Text>
                      <Text as="p" variant="headingLg">
                        €{competitors.competitor_min?.toFixed(2)} – €
                        {competitors.competitor_max?.toFixed(2)}
                      </Text>
                    </BlockStack>
                  </InlineGrid>

                  <Badge
                    tone={
                      competitors.price_position === 'cheapest' ||
                      competitors.price_position === 'below_average'
                        ? 'success'
                        : competitors.price_position === 'most_expensive' ||
                            competitors.price_position === 'above_average'
                          ? 'warning'
                          : 'info'
                    }
                  >
                    {`Position: ${competitors.price_position} (${competitors.price_vs_avg_pct?.toFixed(1) ?? 0}% vs. Ø)`}
                  </Badge>

                  <IndexTable
                    resourceName={{ singular: 'Wettbewerber', plural: 'Wettbewerber' }}
                    headings={[
                      { title: 'Anbieter' },
                      { title: 'Preis' },
                      { title: 'Quelle' },
                      { title: 'Abweichung' },
                    ]}
                    itemCount={compDisplay.length}
                    selectable={false}
                  >
                    {compDisplay.map((c, i) => (
                      <IndexTable.Row key={c.url || i} id={String(i)} position={i}>
                        <IndexTable.Cell>
                          #{i + 1} {c.title}
                        </IndexTable.Cell>
                        <IndexTable.Cell>€{c.price}</IndexTable.Cell>
                        <IndexTable.Cell>{c.source}</IndexTable.Cell>
                        <IndexTable.Cell>
                          <Badge
                            tone={
                              c.price < (competitors.current_price ?? 0)
                                ? 'critical'
                                : 'success'
                            }
                          >
                            {String(
                              c.price < (competitors.current_price ?? 0)
                                ? `${(((c.price - (competitors.current_price ?? 0)) / (competitors.current_price ?? 1)) * 100).toFixed(1)}%`
                                : `+${(((c.price - (competitors.current_price ?? 0)) / (competitors.current_price ?? 1)) * 100).toFixed(1)}%`
                            )}
                          </Badge>
                        </IndexTable.Cell>
                      </IndexTable.Row>
                    ))}
                  </IndexTable>
                </>
              ) : (
                <Text as="p" tone="subdued">
                  Noch keine Wettbewerbsdaten. Suche starten um Konkurrenten zu
                  finden.
                </Text>
              )}

              <Button
                onClick={() => competitorSearchMutation.mutate()}
                loading={competitorSearchMutation.isPending}
              >
                {competitors?.has_data
                  ? 'Wettbewerber aktualisieren'
                  : 'Wettbewerber suchen (Serper)'}
              </Button>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
