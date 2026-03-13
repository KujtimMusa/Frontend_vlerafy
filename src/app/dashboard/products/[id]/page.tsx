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
  Divider,
} from '@shopify/polaris';
import {
  ArrowRightIcon,
  ProductIcon,
  CashEuroIcon,
  PackageIcon,
  CheckIcon,
  RefreshIcon,
} from '@shopify/polaris-icons';
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
      await applyPrice(productId, recommendation.recommended_price, recommendation.id);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['products'] });
      qc.invalidateQueries({ queryKey: ['dashboard-stats'] });
      showToast('Preis erfolgreich übernommen!', { duration: 3000 });
    },
    onError: (err) => showToast(err.message || 'Fehler beim Übernehmen', { isError: true }),
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

  const reasoning = (recommendation?.reasoning_object ?? recommendation?.reasoning) as {
    strategies?: Record<string, { price?: number; confidence?: number; reasoning?: string }>;
  } | undefined;
  const competitorStrategy = reasoning?.strategies?.competitor ?? reasoning?.strategies?.competitive;
  const competitorAvg = recommendation?.competitor_avg_price ?? competitors?.competitor_avg;
  const currentPrice = product?.price ?? recommendation?.current_price ?? 0;
  const recommendedPrice = recommendation?.recommended_price ?? 0;
  const diff = recommendedPrice - currentPrice;
  const diffPct = currentPrice > 0 ? (diff / currentPrice) * 100 : 0;
  const confidence = recommendation?.confidence ?? 0;
  const breakEven = margin?.break_even_price;
  const marginPercent = margin?.margin?.percent ?? 0;
  const inventory = recommendation?.days_of_stock ?? product?.inventory;
  const sales7d = recommendation?.sales_7d ?? 0;
  const hasCostData = margin?.has_cost_data ?? false;
  const hasCompetitorData = competitors?.has_data ?? false;

  const formatPrice = (v: number) =>
    new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(v);

  const compList = competitors?.competitors ?? [];
  const myPrice = competitors?.current_price ?? product?.price ?? 0;
  const compDisplay = compList.map(
    (c: {
      title?: string;
      competitor_name?: string;
      price: number;
      url?: string;
      source?: string;
      competitor_url?: string;
      scraped_at?: string;
    }) => {
      const deviation = myPrice > 0 ? ((c.price - myPrice) / myPrice) * 100 : 0;
      return {
        title: c.title ?? c.competitor_name ?? 'Unbekannt',
        price: c.price,
        source: c.source ?? c.competitor_name ?? '–',
        url: c.url ?? c.competitor_url ?? '',
        scraped_at: c.scraped_at,
        deviation,
      };
    }
  );
  const cheapestCompetitor = compDisplay.length > 0
    ? compDisplay.reduce((a, b) => (a.price < b.price ? a : b))
    : null;
  const cheapestBelowUs = cheapestCompetitor && cheapestCompetitor.price < myPrice;
  const cheapestDeviation = cheapestCompetitor && myPrice > 0
    ? ((cheapestCompetitor.price - myPrice) / myPrice) * 100
    : 0;

  return (
    <Page
      title={product.title}
      backAction={{ content: 'Produkte', url: `/dashboard/products${suffix}` }}
    >
      <Layout>
        <Layout.Section>
          <Card>
            <BlockStack gap="500">
              <Text as="h2" variant="headingMd">
                Preisempfehlung
              </Text>
              {recLoading ? (
                <SkeletonBodyText />
              ) : recommendation ? (
                <>
                  {/* 1. Preis-Vergleich */}
                  <InlineStack align="space-between" blockAlign="center" gap="400">
                    <BlockStack gap="100">
                      <Text as="p" tone="subdued" variant="bodySm">Aktueller Preis</Text>
                      <Text as="p" variant="heading2xl">{formatPrice(currentPrice)}</Text>
                    </BlockStack>
                    <BlockStack gap="0" inlineAlign="center">
                      <ArrowRightIcon />
                      <Badge tone={diff >= 0 ? 'success' : 'critical'}>
                        {`${diff >= 0 ? '▲' : '▼'} ${Math.abs(diffPct).toFixed(1)}%`}
                      </Badge>
                    </BlockStack>
                    <BlockStack gap="100" inlineAlign="end">
                      <Text as="p" tone="subdued" variant="bodySm">Empfohlener Preis</Text>
                      <Text as="p" variant="heading2xl" tone={diff >= 0 ? 'success' : 'critical'}>
                        {formatPrice(recommendedPrice)}
                      </Text>
                    </BlockStack>
                  </InlineStack>

                  {/* 2. Konfidenz-Balken */}
                  <BlockStack gap="200">
                    <InlineStack align="space-between">
                      <Text as="p" variant="bodySm" fontWeight="semibold">Analyse-Sicherheit</Text>
                      <Text as="p" variant="bodySm" tone={confidence >= 0.75 ? 'success' : confidence >= 0.55 ? 'caution' : 'critical'}>
                        {confidence >= 0.75 ? 'Hoch' : confidence >= 0.55 ? 'Mittel' : 'Niedrig'} · {(confidence * 100).toFixed(0)}%
                      </Text>
                    </InlineStack>
                    <ProgressBar
                      progress={confidence * 100}
                      tone={confidence >= 0.75 ? 'success' : confidence >= 0.55 ? 'highlight' : 'critical'}
                      size="medium"
                    />
                    <Text as="p" variant="bodySm" tone="subdued">
                      {confidence >= 0.75
                        ? 'Vollständige Datenbasis – Empfehlung sehr zuverlässig'
                        : confidence >= 0.55
                        ? 'Gute Datenbasis – Verkaufsdaten würden Präzision erhöhen'
                        : 'Lückenhafte Daten – Kostendaten und Verkäufe hinterlegen'}
                    </Text>
                  </BlockStack>

                  <Divider />

                  {/* 3. Warum dieser Preis? */}
                  <Text as="h3" variant="headingSm">Warum dieser Preis?</Text>
                  <BlockStack gap="300">
                    {competitorStrategy && competitorAvg != null && (
                      <div style={{ background: '#F8FAFC', borderRadius: 10, padding: '12px 16px', border: '1px solid #E2E8F0' }}>
                        <InlineStack gap="300" blockAlign="start">
                          <div style={{ width: 36, height: 36, borderRadius: 8, background: '#EEF2FF', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                            <ProductIcon />
                          </div>
                          <BlockStack gap="100">
                            <InlineStack gap="200" blockAlign="center">
                              <Text as="p" variant="bodySm" fontWeight="semibold">Marktposition</Text>
                              <Badge tone="info">{`Wettbewerber Ø ${formatPrice(competitorAvg)}`}</Badge>
                            </InlineStack>
                            <Text as="p" variant="bodySm" tone="subdued">
                              {currentPrice > competitorAvg
                                ? `Dein Preis liegt ${((currentPrice / competitorAvg - 1) * 100).toFixed(0)}% über dem Marktdurchschnitt. Eine Anpassung verbessert die Wettbewerbsfähigkeit.`
                                : `Dein Preis liegt ${((1 - currentPrice / competitorAvg) * 100).toFixed(0)}% unter dem Marktdurchschnitt. Preiserhöhung möglich ohne Wettbewerbsnachteil.`}
                            </Text>
                          </BlockStack>
                        </InlineStack>
                      </div>
                    )}
                    {breakEven != null && (
                      <div style={{ background: '#F8FAFC', borderRadius: 10, padding: '12px 16px', border: '1px solid #E2E8F0' }}>
                        <InlineStack gap="300" blockAlign="start">
                          <div style={{ width: 36, height: 36, borderRadius: 8, background: marginPercent > 20 ? '#F0FDF4' : '#FEF2F2', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                            <CashEuroIcon />
                          </div>
                          <BlockStack gap="100">
                            <InlineStack gap="200" blockAlign="center">
                              <Text as="p" variant="bodySm" fontWeight="semibold">Marge & Rentabilität</Text>
                              <Badge tone={marginPercent > 20 ? 'success' : 'critical'}>{`${marginPercent.toFixed(1)}% Marge`}</Badge>
                            </InlineStack>
                            <Text as="p" variant="bodySm" tone="subdued">
                              Break-Even bei {formatPrice(breakEven)}.
                              {recommendedPrice > breakEven
                                ? ` Empfohlener Preis sichert ${(((recommendedPrice - breakEven) / recommendedPrice) * 100).toFixed(1)}% Marge.`
                                : ' ⚠️ Empfohlener Preis liegt unter Break-Even – Schutzregel aktiv.'}
                            </Text>
                          </BlockStack>
                        </InlineStack>
                      </div>
                    )}
                    {inventory != null && inventory !== undefined && (
                      <div style={{ background: '#F8FAFC', borderRadius: 10, padding: '12px 16px', border: '1px solid #E2E8F0' }}>
                        <InlineStack gap="300" blockAlign="start">
                          <div style={{ width: 36, height: 36, borderRadius: 8, background: '#FFFBEB', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                            <PackageIcon />
                          </div>
                          <BlockStack gap="100">
                            <InlineStack gap="200" blockAlign="center">
                              <Text as="p" variant="bodySm" fontWeight="semibold">Lagerbestand</Text>
                              <Badge tone={inventory > 20 ? 'success' : inventory > 5 ? 'warning' : 'critical'}>{`${inventory} Stück`}</Badge>
                            </InlineStack>
                            <Text as="p" variant="bodySm" tone="subdued">
                              {inventory > 50
                                ? 'Hoher Lagerbestand – kein Abverkaufsdruck, Preis kann stabil bleiben oder steigen.'
                                : inventory > 10
                                ? 'Normaler Lagerbestand – Preis basiert auf Markt und Marge.'
                                : 'Niedriger Lagerbestand – Knappheit kann höheren Preis rechtfertigen.'}
                            </Text>
                          </BlockStack>
                        </InlineStack>
                      </div>
                    )}
                    {confidence < 0.75 && (
                      <div style={{ background: '#FFFBEB', borderRadius: 10, padding: '12px 16px', border: '1px solid #FDE68A' }}>
                        <BlockStack gap="100">
                          <Text as="p" variant="bodySm" fontWeight="semibold" tone="caution">💡 Empfehlung verbessern</Text>
                          <Text as="p" variant="bodySm" tone="subdued">
                            {!hasCostData && '- Kostendaten eintragen → Break-Even-Schutz aktiv\n'}
                            {sales7d === 0 && '- Erste Verkäufe abwarten → Nachfrageanalyse wird präziser\n'}
                            {!hasCompetitorData && '- Wettbewerber aktualisieren → Marktvergleich verbessert Empfehlung'}
                          </Text>
                        </BlockStack>
                      </div>
                    )}
                  </BlockStack>

                  <Divider />

                  <Text as="h3" variant="headingMd">Begründung</Text>
                  <Text as="p">{reasoningText}</Text>

                  <InlineStack gap="300">
                    <Button variant="primary" onClick={() => applyMutation.mutate()} loading={applyMutation.isPending} icon={CheckIcon}>
                      Preis übernehmen ({formatPrice(recommendedPrice)})
                    </Button>
                    <Button onClick={() => generateMutation.mutate()} loading={generateMutation.isPending} icon={RefreshIcon}>
                      Neu analysieren
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

                  <Divider />

                  <Text as="h3" variant="headingMd">Rentabilitäts-Übersicht</Text>
                  <InlineGrid columns={{ xs: 2, md: 4 }} gap="300">
                    {[
                      { label: 'Nettoumsatz', value: formatPrice(margin.net_revenue), hint: 'Nach MwSt-Abzug' },
                      { label: 'Rohgewinn', value: formatPrice(margin.margin.euro), tone: margin.margin.euro > 0 ? 'success' : 'critical' },
                      { label: 'Marge', value: margin.margin.percent.toFixed(1) + '%', tone: margin.margin.percent >= 20 ? 'success' : 'critical' },
                      { label: 'ROI', value: (margin.costs.total_variable > 0 ? (margin.margin.euro / margin.costs.total_variable) * 100 : 0).toFixed(0) + '%', hint: 'Return on Investment' },
                    ].map((item, i) => (
                      <BlockStack key={i} gap="100">
                        <Text as="p" tone="subdued" variant="bodySm">{item.label}</Text>
                        <Text as="p" variant="headingLg" tone={item.tone as 'success' | 'critical' | undefined}>{item.value}</Text>
                        {item.hint && <Text as="p" variant="bodySm" tone="subdued">{item.hint}</Text>}
                      </BlockStack>
                    ))}
                  </InlineGrid>

                  <Text as="h3" variant="headingMd">Preis-Szenarien</Text>
                  <Text as="p" tone="subdued" variant="bodySm">Was passiert bei verschiedenen Preisen?</Text>
                  <BlockStack gap="100">
                    {[
                      { label: 'Break-Even', price: margin.break_even_price, margin: 0 },
                      { label: 'Ziel-Marge (20%)', price: margin.recommended_min_price, margin: 20 },
                      { label: 'Aktueller Preis', price: margin.selling_price, margin: margin.margin.percent, highlight: true },
                      ...(recommendation ? [{ label: 'Empfohlener Preis', price: recommendation.recommended_price, margin: ((recommendation.recommended_price / (1 + (margin.vat_rate || 19) / 100) - margin.costs.total_variable) / (recommendation.recommended_price / (1 + (margin.vat_rate || 19) / 100))) * 100 }] : []),
                      ...(competitors?.competitor_avg ? [{ label: 'Wettbewerber Ø', price: competitors.competitor_avg, margin: ((competitors.competitor_avg / (1 + (margin.vat_rate || 19) / 100) - margin.costs.total_variable) / (competitors.competitor_avg / (1 + (margin.vat_rate || 19) / 100))) * 100 }] : []),
                    ].map((scenario, i) => (
                      <div key={i} style={{ padding: '8px 12px', background: (scenario as { highlight?: boolean }).highlight ? '#F5F3FF' : 'transparent', borderRadius: 6 }}>
                      <InlineStack align="space-between" gap="200" blockAlign="center">
                        <Text as="p" variant="bodySm">{(scenario as { label: string }).label}</Text>
                        <Text as="p" variant="bodySm" fontWeight="semibold">{formatPrice((scenario as { price: number }).price)}</Text>
                        <Badge tone={((scenario as { margin: number }).margin >= 20 ? 'success' : (scenario as { margin: number }).margin >= 0 ? 'warning' : 'critical') as 'success' | 'warning' | 'critical'}>
                          {`${(scenario as { margin: number }).margin.toFixed(1)}% Marge`}
                        </Badge>
                      </InlineStack>
                      </div>
                    ))}
                  </BlockStack>

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
                      <Text as="p" tone="subdued">Dein Preis</Text>
                      <Text as="p" variant="headingLg">{formatPrice(competitors.current_price)}</Text>
                    </BlockStack>
                    <BlockStack gap="100">
                      <Text as="p" tone="subdued">Marktdurchschnitt</Text>
                      <Text as="p" variant="headingLg">{formatPrice(competitors.competitor_avg ?? 0)}</Text>
                      <Text as="p" tone="subdued">{competitors.competitor_count} Anbieter</Text>
                    </BlockStack>
                    <BlockStack gap="100">
                      <Text as="p" tone="subdued">Preisspanne</Text>
                      <Text as="p" variant="headingLg">
                        {formatPrice(competitors.competitor_min ?? 0)} – {formatPrice(competitors.competitor_max ?? 0)}
                      </Text>
                    </BlockStack>
                  </InlineGrid>

                  {/* Marktposition visuell */}
                  {competitors.competitor_min != null && competitors.competitor_max != null && competitors.competitor_avg != null && (
                    <Card>
                      <BlockStack gap="300">
                        <Text as="h3" variant="headingMd">Marktposition</Text>
                        <div style={{ position: 'relative', height: 60 }}>
                          <div style={{ position: 'absolute', top: 24, left: 0, right: 0, height: 8, background: '#E2E8F0', borderRadius: 4 }} />
                          {(() => {
                            const minP = competitors.competitor_min!;
                            const maxP = competitors.competitor_max!;
                            const range = maxP - minP || 1;
                            const toPercent = (p: number) => Math.min(100, Math.max(0, ((p - minP) / range) * 100));
                            const avgLeft = toPercent(competitors.competitor_avg!);
                            const myLeft = toPercent(myPrice);
                            return (
                              <>
                                <div style={{ position: 'absolute', top: 24, height: 8, left: 0, width: '100%', background: 'linear-gradient(90deg, #86EFAC, #4ADE80)', borderRadius: 4, opacity: 0.6 }} />
                                <div style={{ position: 'absolute', left: `${avgLeft}%`, top: 16, transform: 'translateX(-50%)', width: 4, height: 24, background: '#10B981', borderRadius: 2 }} title={`Marktdurchschnitt: ${formatPrice(competitors.competitor_avg!)}`} />
                                <div style={{ position: 'absolute', left: `${myLeft}%`, top: 14, transform: 'translateX(-50%)', width: 20, height: 20, borderRadius: '50%', background: '#6366F1', border: '3px solid white', boxShadow: '0 0 0 2px #6366F1' }} title={`Dein Preis: ${formatPrice(myPrice)}`} />
                              </>
                            );
                          })()}
                        </div>
                        <InlineStack gap="400">
                          <InlineStack gap="100">
                            <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#6366F1' }} />
                            <Text as="p" variant="bodySm">Dein Preis {formatPrice(myPrice)}</Text>
                          </InlineStack>
                          <InlineStack gap="100">
                            <div style={{ width: 12, height: 4, background: '#10B981', marginTop: 4, borderRadius: 2 }} />
                            <Text as="p" variant="bodySm">Markt Ø {formatPrice(competitors.competitor_avg!)}</Text>
                          </InlineStack>
                        </InlineStack>
                        <Banner tone={(() => {
                          const avg = competitors.competitor_avg ?? 0;
                          if (avg <= 0) return 'info';
                          return myPrice > avg * 1.1 ? 'warning' : myPrice < avg * 0.9 ? 'info' : 'success';
                        })()}>
                          {(() => {
                            const avg = competitors.competitor_avg ?? 0;
                            if (avg <= 0) return 'Kein Marktdurchschnitt verfügbar.';
                            if (myPrice > avg * 1.1) return `Dein Preis liegt ${((myPrice / avg - 1) * 100).toFixed(0)}% über dem Marktdurchschnitt – prüfe ob dein Produkt diesen Aufpreis rechtfertigt.`;
                            if (myPrice < avg * 0.9) return `Dein Preis liegt ${((1 - myPrice / avg) * 100).toFixed(0)}% unter dem Marktdurchschnitt – Potenzial für Preiserhöhung vorhanden.`;
                            return 'Dein Preis liegt im Marktdurchschnitt – gute Wettbewerbsposition.';
                          })()}
                        </Banner>
                      </BlockStack>
                    </Card>
                  )}

                  <IndexTable
                    resourceName={{ singular: 'Wettbewerber', plural: 'Wettbewerber' }}
                    headings={[
                      { title: 'Anbieter' },
                      { title: 'Preis' },
                      { title: 'Abweichung' },
                      { title: 'Quelle' },
                      { title: 'Letzte Abfrage' },
                    ]}
                    itemCount={compDisplay.length}
                    selectable={false}
                  >
                    {compDisplay.map((c, i) => (
                      <IndexTable.Row key={c.url || i} id={String(i)} position={i}>
                        <IndexTable.Cell>#{i + 1} {c.title}</IndexTable.Cell>
                        <IndexTable.Cell>{formatPrice(c.price)}</IndexTable.Cell>
                        <IndexTable.Cell>
                          <Badge tone={(c.deviation > 10 ? 'critical' : c.deviation < -10 ? 'success' : 'warning') as 'critical' | 'success' | 'warning'}>
                            {`${c.deviation > 0 ? '▲' : '▼'} ${Math.abs(c.deviation).toFixed(1)}%`}
                          </Badge>
                        </IndexTable.Cell>
                        <IndexTable.Cell>{c.source}</IndexTable.Cell>
                        <IndexTable.Cell>
                          {c.scraped_at ? (
                            <Text as="p" variant="bodySm" tone="subdued">
                              {new Date(c.scraped_at).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' })}
                            </Text>
                          ) : (
                            <Text as="p" variant="bodySm" tone="subdued">–</Text>
                          )}
                        </IndexTable.Cell>
                      </IndexTable.Row>
                    ))}
                  </IndexTable>

                  {compDisplay.length > 0 && (
                    <Card>
                      <BlockStack gap="100">
                        <Text as="h3" variant="headingSm">Handlungsempfehlung</Text>
                        <Text as="p" tone="subdued" variant="bodySm">
                          {cheapestBelowUs && cheapestCompetitor
                            ? `${cheapestCompetitor.title} bietet ${formatPrice(cheapestCompetitor.price)} an – ${Math.abs(cheapestDeviation).toFixed(0)}% günstiger als du. Prüfe ob Qualitätsunterschiede den Preisabstand rechtfertigen.`
                            : 'Du bist einer der günstigsten Anbieter. Preiserhöhung auf Ø ' + formatPrice(competitors.competitor_avg ?? 0) + ' möglich ohne Wettbewerbsnachteil.'}
                        </Text>
                      </BlockStack>
                    </Card>
                  )}
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
