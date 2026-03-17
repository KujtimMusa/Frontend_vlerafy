'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useSearchParams } from 'next/navigation';
import { useState, useEffect, useRef } from 'react';
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
  explainPrice,
  chatWithAI,
  getCategoryDefaults,
} from '@/lib/api';
import { showToast } from '@/lib/toast';
import type { Recommendation } from '@/types/models';
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

function extractReasoningText(reasoning: unknown): string | null {
  if (reasoning == null) return null;
  if (typeof reasoning === 'string') return reasoning;
  if (typeof reasoning === 'object' && reasoning !== null) {
    const obj = reasoning as Record<string, unknown>;
    const text = obj.text ?? obj.explanation ?? obj.summary;
    if (typeof text === 'string') return text;
  }
  return null;
}

export default function ProductDetailPage() {
  const { id } = useParams();
  const productId = Number(id);
  const qc = useQueryClient();
  const suffix = useShopSuffix();

  type PaymentProvider = 'stripe' | 'paypal' | 'klarna' | 'custom';
  const initialCostForm: {
    purchase_cost: string;
    shipping_cost: string;
    packaging_cost: string;
    payment_provider: PaymentProvider;
    payment_fee_percentage: string;
    payment_fee_fixed: string;
    country_code: string;
    category: string;
  } = {
    purchase_cost: '',
    shipping_cost: '',
    packaging_cost: '',
    payment_provider: 'stripe',
    payment_fee_percentage: '2.9',
    payment_fee_fixed: '0.30',
    country_code: 'DE',
    category: 'fashion',
  };
  const [costForm, setCostForm] = useState(initialCostForm);
  const [costFormDirty, setCostFormDirty] = useState(false);
  const [aiExplanation, setAiExplanation] = useState<{
    explanation: string;
    key_reason: string;
    confidence_text: string;
    action_hint: string;
  } | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [_aiError, setAiError] = useState(false);
  const [chatMessages, setChatMessages] = useState<
    Array<{ role: 'user' | 'assistant'; content: string }>
  >([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);

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
        payment_provider: (existingCosts.payment_provider || 'stripe') as PaymentProvider,
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
      setCostFormDirty(false);
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

  // ✅ BFS [Punkt 4] erledigt — Contextual Save Bar für Kostenformular
  const handleCostDiscard = () => {
    if (existingCosts) {
      setCostForm({
        purchase_cost: String(existingCosts.purchase_cost),
        shipping_cost: String(existingCosts.shipping_cost),
        packaging_cost: String(existingCosts.packaging_cost),
        payment_provider: (existingCosts.payment_provider || 'stripe') as PaymentProvider,
        payment_fee_percentage: String(existingCosts.payment_fee_percentage),
        payment_fee_fixed: String(existingCosts.payment_fee_fixed),
        country_code: existingCosts.country_code,
        category: existingCosts.category ?? 'fashion',
      });
    } else {
      setCostForm({ ...initialCostForm });
    }
    setCostFormDirty(false);
  };

  const loadCategoryDefaults = async (category: string) => {
    const defaults = await getCategoryDefaults(category);
    setCostFormDirty(true);
    setCostForm((prev) => ({
      ...prev,
      category,
      shipping_cost: String(defaults.shipping_estimate),
      packaging_cost: String(defaults.packaging_estimate),
    }));
  };

  const handleAiExplain = async () => {
    if (!recommendation) return;
    setAiLoading(true);
    setAiError(false);
    try {
      const result = await explainPrice({
        current_price: recommendation.current_price,
        recommended_price: recommendation.recommended_price,
        confidence: recommendation.confidence ?? 0,
        price_change_pct: recommendation.price_change_pct ?? 0,
        strategies: recommendation.reasoning_object?.strategies as Record<string, unknown> | undefined,
        competitor_avg: recommendation.competitor_avg_price,
        break_even: margin?.break_even_price,
        inventory: product?.inventory ?? recommendation?.days_of_stock ?? undefined,
        product_title: product?.title,
        currency: 'EUR',
      });
      setAiExplanation(result);
    } catch (err) {
      console.error('[KI DEBUG] handleAiExplain Fehler:', err);
      setAiError(true);
    } finally {
      setAiLoading(false);
    }
  };

  const handleChatSend = async () => {
    const msg = chatInput.trim();
    if (!msg || chatLoading) return;
    const newMessages = [
      ...chatMessages,
      { role: 'user' as const, content: msg },
    ];
    setChatMessages(newMessages);
    setChatInput('');
    setChatLoading(true);
    try {
      const result = await chatWithAI({
        message: msg,
        product_title: product?.title,
        current_price: recommendation?.current_price,
        recommended_price: recommendation?.recommended_price,
        confidence: recommendation?.confidence,
        competitor_avg: recommendation?.competitor_avg_price,
        break_even: margin?.break_even_price,
        history: chatMessages.slice(-6),
      });
      setChatMessages([
        ...newMessages,
        { role: 'assistant', content: result.reply },
      ]);
    } catch (err) {
      console.error('[KI DEBUG] handleChatSend Fehler:', err);
      setChatMessages([
        ...newMessages,
        {
          role: 'assistant',
          content:
            'Tut mir leid, ich konnte deine Frage gerade nicht beantworten.',
        },
      ]);
    } finally {
      setChatLoading(false);
      setTimeout(
        () => chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' }),
        100
      );
    }
  };

  const formatPrice = (v: number) =>
    new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(v);

  if (!product) {
    const suffix = typeof window !== 'undefined'
      ? (new URLSearchParams(window.location.search).get('shop') ? `?shop=${new URLSearchParams(window.location.search).get('shop')}` : '')
      : '';
    return (
      <s-page
        title="Produkt laden…"
        back-action={JSON.stringify({ content: 'Produkte', url: `/dashboard/products${suffix}` })}
      >
        <div className="vlerafy-skeleton vlerafy-skeleton-title" />
        <div className="vlerafy-skeleton vlerafy-skeleton-text vlerafy-skeleton-text--40" />
        <div className="vlerafy-skeleton vlerafy-skeleton-card vlerafy-detail-card" />
      </s-page>
    );
  }

  const productExt = product as unknown as Record<string, unknown>;
  const vendor = (productExt.vendor as string) ?? '—';
  const productType = (productExt.product_type as string) ?? product.category ?? '—';

  const currentPrice = product?.price ?? recommendation?.current_price ?? 0;
  const recommendedPrice = recommendation?.recommended_price ?? 0;
  const diff = recommendedPrice - currentPrice;
  const diffPct = currentPrice > 0 ? (diff / currentPrice) * 100 : 0;
  const confidence = recommendation?.confidence ?? 0;
  const confidencePct = Math.round(confidence * 100);

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

  const minPrice = competitors?.competitor_min ?? 0;
  const maxPrice = competitors?.competitor_max ?? 1;
  const range = maxPrice - minPrice || 1;
  const positionPct = Math.min(100, Math.max(0, ((myPrice - minPrice) / range) * 100));

  const competition = {
    avgPrice: competitors?.competitor_avg ?? 0,
    minPrice,
    maxPrice: competitors?.competitor_max ?? 0,
    count: competitors?.competitor_count ?? 0,
    positionPct,
    competitors: compDisplay.map((c) => ({
      name: c.title,
      price: c.price,
      diff: c.deviation,
      source: c.source,
      lastUpdated: c.scraped_at ? new Date(c.scraped_at).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' }) : '–',
    })),
    recommendation: cheapestBelowUs && cheapestCompetitor
      ? `${cheapestCompetitor.title} bietet ${formatPrice(cheapestCompetitor.price)} an – ${Math.abs(cheapestDeviation).toFixed(0)}% günstiger als du. Prüfe ob Qualitätsunterschiede den Preisabstand rechtfertigen.`
      : compDisplay.length > 0
        ? `Du bist einer der günstigsten Anbieter. Preiserhöhung auf Ø ${formatPrice(competitors?.competitor_avg ?? 0)} möglich ohne Wettbewerbsnachteil.`
        : null,
  };

  const reasoningDisplay = extractReasoningText(recommendation?.reasoning);
  const reasoningFallback = reasoningDisplay == null && recommendation?.reasoning != null;

  return (
    <>
      {costFormDirty && (
        <s-contextual-save-bar
          message="Nicht gespeicherte Änderungen"
          onSave={() => saveCostsMutation.mutate()}
          onDiscard={handleCostDiscard}
          saveLoading={saveCostsMutation.isPending}
        />
      )}
      <s-page
        title={product.title}
        back-action={JSON.stringify({ content: 'Produkte', url: `/dashboard/products${suffix}` })}
      >
        <div className="vlerafy-main">
          <div className="vlerafy-page-header">
        <s-stack direction="inline" align-items="center" justify-content="space-between">
          <div>
            <s-paragraph tone="subdued">{vendor} · {productType}</s-paragraph>
          </div>
          <s-stack direction="inline" gap="2">
            <s-button
              variant="secondary"
              size="slim"
              onClick={() => generateMutation.mutate()}
              loading={generateMutation.isPending}
            >
              Neu analysieren
            </s-button>
            {recommendation && (
              <s-button
                variant="primary"
                size="slim"
                onClick={() => applyMutation.mutate()}
                loading={applyMutation.isPending}
              >
                Preis übernehmen
              </s-button>
            )}
          </s-stack>
        </s-stack>
      </div>

      <div className="vlerafy-detail-grid">
        <div className="vlerafy-detail-left">
          <div className="vlerafy-card-wrapper vlerafy-detail-card">
            <div className="vlerafy-card-inner">
              <p className="vlerafy-section-label">Preisempfehlung</p>
              {recLoading ? (
                <div className="vlerafy-skeleton vlerafy-skeleton-text" style={{ height: 80 }} />
              ) : recommendation ? (
                <>
                  <s-stack direction="inline" align-items="flex-end" gap="4" style={{ margin: '12px 0' }}>
                    <div>
                      <p className="vlerafy-price-current">Aktuell: {currentPrice.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €</p>
                      <p className="vlerafy-price-recommended">{recommendedPrice.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €</p>
                    </div>
                    <div className={`vlerafy-price-change-badge ${diff >= 0 ? 'vlerafy-price-change-badge--up' : 'vlerafy-price-change-badge--down'}`}>
                      {diff >= 0 ? '▲' : '▼'} {Math.abs(diffPct).toFixed(1)}%
                    </div>
                  </s-stack>

                  <s-stack direction="inline" align-items="center" gap="3" style={{ marginBottom: '16px' }}>
                    <span className="vlerafy-kpi-label">Analyse-Sicherheit</span>
                    <div className="vlerafy-confidence-bar">
                      <div
                        className="vlerafy-confidence-fill"
                        style={{ width: `${confidencePct}%` }}
                      />
                    </div>
                    <span className="vlerafy-confidence-value">{confidencePct}%</span>
                  </s-stack>

                  <s-stack direction="inline" gap="2">
                    <s-button variant="primary" onClick={() => applyMutation.mutate()} loading={applyMutation.isPending}>
                      Preis übernehmen ({recommendedPrice.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €)
                    </s-button>
                    <s-button variant="plain" size="slim" onClick={handleAiExplain} disabled={aiLoading}>
                      Warum dieser Preis?
                    </s-button>
                  </s-stack>
                </>
              ) : (
                <s-stack direction="block" gap="4" style={{ marginTop: 12 }}>
                  <s-paragraph tone="subdued">Noch keine Empfehlung für dieses Produkt.</s-paragraph>
                  <s-button variant="primary" onClick={() => generateMutation.mutate()} loading={generateMutation.isPending}>
                    Empfehlung generieren
                  </s-button>
                </s-stack>
              )}
            </div>
          </div>

          {(product.inventory ?? 0) === 0 && (
            <div className="vlerafy-detail-card">
              <s-banner tone="warning">
                Kein Lagerbestand – Knappheit kann einen höheren Preis rechtfertigen.
              </s-banner>
            </div>
          )}

          <div className="vlerafy-card-wrapper vlerafy-detail-card">
            <div className="vlerafy-card-inner">
              <p className="vlerafy-section-label">Margen-Analyse</p>
              <s-stack direction="inline" gap="4" style={{ marginTop: '12px' }}>
                <div>
                  <s-select
                    label="Kategorie"
                    value={costForm.category}
                    options={JSON.stringify(CATEGORIES.map(c => ({ label: c.label, value: c.value })))}
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    onChange={(e: any) => loadCategoryDefaults(e?.target?.value ?? e?.detail?.value ?? '')}
                  />
                </div>
                <div>
                  <s-select
                    label="Zahlungsanbieter"
                    value={costForm.payment_provider}
                    options={JSON.stringify(PAYMENT_PROVIDERS.map(c => ({ label: c.label, value: c.value })))}
                    onChange={(e: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
                      setCostFormDirty(true);
                      setCostForm((p) => ({ ...p, payment_provider: (e?.target?.value ?? e?.detail?.value ?? '') as PaymentProvider }));
                    }}
                  />
                </div>
              </s-stack>
            </div>
          </div>

          <div className="vlerafy-card-wrapper vlerafy-detail-card">
            <div className="vlerafy-card-inner">
              <p className="vlerafy-section-label">Wettbewerbsanalyse</p>
              {compLoading ? (
                <div className="vlerafy-skeleton vlerafy-skeleton-text" style={{ height: 100 }} />
              ) : competitors?.has_data ? (
                <>
                  <div className="vlerafy-market-stats">
                    <div className="vlerafy-market-stat">
                      <p className="vlerafy-kpi-label">Dein Preis</p>
                      <p className="vlerafy-kpi-value">{myPrice.toLocaleString('de-DE', { minimumFractionDigits: 2 })} €</p>
                    </div>
                    <div className="vlerafy-market-stat">
                      <p className="vlerafy-kpi-label">Marktdurchschnitt</p>
                      <p className="vlerafy-kpi-value">{competition.avgPrice.toLocaleString('de-DE', { minimumFractionDigits: 2 })} €</p>
                    </div>
                    <div className="vlerafy-market-stat">
                      <p className="vlerafy-kpi-label">Preisspanne</p>
                      <p className="vlerafy-kpi-value">{competition.minPrice.toLocaleString('de-DE', { minimumFractionDigits: 2 })} – {competition.maxPrice.toLocaleString('de-DE', { minimumFractionDigits: 2 })} €</p>
                    </div>
                    <div className="vlerafy-market-stat">
                      <p className="vlerafy-kpi-label">Anbieter</p>
                      <p className="vlerafy-kpi-value">{competition.count}</p>
                    </div>
                  </div>

                  <div className="vlerafy-market-position vlerafy-detail-card">
                    <p className="vlerafy-kpi-label vlerafy-mb-8">Marktposition</p>
                    <div className="vlerafy-market-bar">
                      <div
                        className="vlerafy-market-indicator"
                        style={{ left: `${competition.positionPct}%` }}
                      />
                    </div>
                    <s-stack direction="inline" justify-content="space-between" style={{ marginTop: '6px' }}>
                      <span className="vlerafy-kpi-label">{competition.minPrice.toLocaleString('de-DE', { minimumFractionDigits: 2 })} € (günstigster)</span>
                      <span className="vlerafy-kpi-label">{competition.maxPrice.toLocaleString('de-DE', { minimumFractionDigits: 2 })} € (teuerster)</span>
                    </s-stack>
                  </div>

                  <div className="vlerafy-table-wrapper">
                    <table className="vlerafy-table">
                      <thead>
                        <tr>
                          <th>Anbieter</th>
                          <th>Preis</th>
                          <th>Abweichung</th>
                          <th>Quelle</th>
                          <th>Letzte Abfrage</th>
                        </tr>
                      </thead>
                      <tbody>
                        {competition.competitors.map((c, idx) => (
                          <tr key={`${c.name}-${idx}`}>
                            <td>#{idx + 1} {c.name}</td>
                            <td className="vlerafy-table-price">{c.price.toLocaleString('de-DE', { minimumFractionDigits: 2 })} €</td>
                            <td>
                              <span className={c.diff > 0 ? 'vlerafy-diff-up' : 'vlerafy-diff-down'}>
                                {c.diff > 0 ? '▲' : '▼'} {Math.abs(c.diff).toFixed(1)}%
                              </span>
                            </td>
                            <td className="vlerafy-table-muted">{c.source}</td>
                            <td className="vlerafy-table-muted">{c.lastUpdated}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {competition.recommendation && (
                    <div className="vlerafy-insight-box vlerafy-detail-card">
                      <span className="vlerafy-insight-icon">💡</span>
                      <p className="vlerafy-insight-text">{competition.recommendation}</p>
                    </div>
                  )}
                </>
              ) : (
                <>
                  <s-paragraph tone="subdued" className="vlerafy-mt-12">
                    Noch keine Wettbewerbsdaten. Suche starten um Konkurrenten zu finden.
                  </s-paragraph>
                  <s-button
                    variant="primary"
                    onClick={() => competitorSearchMutation.mutate()}
                    loading={competitorSearchMutation.isPending}
                    className="vlerafy-mt-12"
                  >
                    {competitors?.has_data ? 'Wettbewerber aktualisieren' : 'Wettbewerber suchen (Serper)'}
                  </s-button>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="vlerafy-detail-right">
          <div className="vlerafy-card-wrapper vlerafy-detail-card">
            <div className="vlerafy-card-inner">
              <p className="vlerafy-section-label">Preisentwicklung – Letzte 30 Tage</p>
              <div className="vlerafy-mt-12">
                <PreisverlaufChart
                  data={chartData}
                  title="Preisentwicklung"
                  subtitle="Letzte 30 Tage"
                />
              </div>
            </div>
          </div>

          {recommendation && (
            <div className="vlerafy-ai-container">
              <div className="vlerafy-ai-header">
                <span className="vlerafy-ai-emoji">✨</span>
                <span className="vlerafy-ai-header-title">KI-Erklärung</span>
                {!aiExplanation && (
                  <s-button
                    variant="plain"
                    size="slim"
                    className="vlerafy-ai-header-btn vlerafy-ai-header-btn--load"
                    onClick={handleAiExplain}
                  >
                    {aiLoading ? 'Analysiere...' : 'Erklärung laden ✨'}
                  </s-button>
                )}
                {aiExplanation && (
                  <s-button
                    variant="plain"
                    size="slim"
                    className="vlerafy-ai-header-btn vlerafy-ai-header-btn--reset"
                    onClick={() => setAiExplanation(null)}
                  >
                    Zurücksetzen
                  </s-button>
                )}
              </div>
              {aiExplanation && (
                <div className="vlerafy-ai-explanation">
                  <div className="vlerafy-ai-explanation-main">
                    <p className="vlerafy-ai-explanation-text">{aiExplanation.explanation}</p>
                  </div>
                  <div className="vlerafy-ai-explanation-meta">
                    <div className="vlerafy-ai-meta-item">
                      <span className="vlerafy-ai-meta-label">Hauptgrund</span>
                      <span className="vlerafy-ai-meta-value">{aiExplanation.key_reason}</span>
                    </div>
                    <div className="vlerafy-ai-meta-item">
                      <span className="vlerafy-ai-meta-label">Sicherheit</span>
                      <span className="vlerafy-ai-meta-value">{aiExplanation.confidence_text}</span>
                    </div>
                    <div className="vlerafy-ai-meta-item">
                      <span className="vlerafy-ai-meta-label">Empfehlung</span>
                      <span className="vlerafy-ai-meta-value">{aiExplanation.action_hint}</span>
                    </div>
                  </div>
                </div>
              )}
              <div className="vlerafy-chat-messages">
                {chatMessages.map((msg, i) => (
                  <div
                    key={i}
                    className={msg.role === 'user' ? 'vlerafy-chat-bubble-user' : 'vlerafy-chat-bubble-ai'}
                  >
                    {msg.content}
                  </div>
                ))}
                {chatLoading && (
                  <s-stack direction="inline" gap="2" className="vlerafy-stack-center">
                    <s-spinner size="small" />
                    <s-paragraph tone="subdued">KI denkt nach...</s-paragraph>
                  </s-stack>
                )}
                {reasoningDisplay && (
                  <div className="vlerafy-reasoning-block">{reasoningDisplay}</div>
                )}
                {reasoningFallback && (
                  <pre className="vlerafy-reasoning-block">
                    {JSON.stringify(recommendation.reasoning, null, 2)}
                  </pre>
                )}
                <div ref={chatBottomRef} />
              </div>
              <div className="vlerafy-chat-input-row">
                <s-text-field
                  label=""
                  placeholder="Frage zur Preisempfehlung..."
                  value={chatInput}
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  onChange={(e: any) =>
                    setChatInput(e?.target?.value ?? e?.detail?.value ?? '')
                  }
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  onKeyDown={(e: any) => e.key === 'Enter' && handleChatSend()}
                />
                <s-button variant="primary" size="slim" onClick={handleChatSend} disabled={!chatInput.trim() || chatLoading}>
                  Senden
                </s-button>
              </div>
            </div>
          )}
        </div>
      </div>
        </div>
      </s-page>
    </>
  );
}
