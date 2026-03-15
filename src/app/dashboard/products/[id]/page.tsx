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
import { useRouter } from 'next/navigation';
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
  const router = useRouter();
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
  const [aiExplanation, setAiExplanation] = useState<{
    explanation: string;
    key_reason: string;
    confidence_text: string;
    action_hint: string;
  } | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState(false);
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
    } catch {
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
    } catch {
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

  if (!product) {
    return (
      <div className="vlerafy-main">
        <div className="vlerafy-page-header">
          <div className="vlerafy-skeleton vlerafy-skeleton-title" />
          <div className="vlerafy-skeleton vlerafy-skeleton-text" style={{ width: '40%' }} />
        </div>
        <div className="vlerafy-skeleton vlerafy-skeleton-card" style={{ marginTop: 24 }} />
      </div>
    );
  }

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
    <div className="vlerafy-main">
      <div className="vlerafy-page-header" style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <s-button variant="plain" onClick={() => router.push(`/dashboard/products${suffix}`)}>
          ← Produkte
        </s-button>
        <h1 className="vlerafy-page-title">{product.title}</h1>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(300px,380px)', gap: 24, alignItems: 'start' }}>
        <div>
      <s-section>
        <s-stack direction="block" gap="5">
          <s-heading size="md">Preisempfehlung</s-heading>
          {recLoading ? (
            <div className="vlerafy-skeleton vlerafy-skeleton-text" style={{ height: 80 }} />
              ) : recommendation ? (
                <>
                  {/* 1. Preis-Vergleich */}
                  <s-stack direction="inline" style={{ justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
                    <s-stack direction="block" gap="1">
                      <s-paragraph tone="subdued" style={{ fontSize: 13 }}>Aktueller Preis</s-paragraph>
                      <s-heading size="2xl">{formatPrice(currentPrice)}</s-heading>
                    </s-stack>
                    <s-stack direction="block" style={{ alignItems: 'center' }}>
                      <span style={{ color: 'var(--v-gray-400)' }}>→</span>
                      <s-badge tone={diff >= 0 ? 'success' : 'critical'}>
                        {`${diff >= 0 ? '▲' : '▼'} ${Math.abs(diffPct).toFixed(1)}%`}
                      </s-badge>
                    </s-stack>
                    <s-stack direction="block" gap="1" style={{ alignItems: 'flex-end' }}>
                      <s-paragraph tone="subdued" style={{ fontSize: 13 }}>Empfohlener Preis</s-paragraph>
                      <s-text style={{ fontSize: 24, fontWeight: 700, color: diff >= 0 ? 'var(--v-success)' : 'var(--v-critical)' }}>
                        {formatPrice(recommendedPrice)}
                      </s-text>
                    </s-stack>
                  </s-stack>

                  {/* 2. Konfidenz-Balken */}
                  <s-stack direction="block" gap="2">
                    <s-stack direction="inline" style={{ justifyContent: 'space-between' }}>
                      <s-text fontWeight="600" style={{ fontSize: 13 }}>Analyse-Sicherheit</s-text>
                      <s-text style={{ fontSize: 13, color: confidence >= 0.75 ? 'var(--v-success)' : confidence >= 0.55 ? 'var(--v-warning)' : 'var(--v-critical)' }}>
                        {confidence >= 0.75 ? 'Hoch' : confidence >= 0.55 ? 'Mittel' : 'Niedrig'} · {(confidence * 100).toFixed(0)}%
                      </s-text>
                    </s-stack>
                    <div className="vlerafy-progress">
                      <div
                        className={`vlerafy-progress-bar ${confidence >= 0.75 ? 'vlerafy-progress-bar--success' : confidence >= 0.55 ? 'vlerafy-progress-bar--warning' : 'vlerafy-progress-bar--critical'}`}
                        style={{ width: `${confidence * 100}%` }}
                      />
                    </div>
                    <s-paragraph tone="subdued" style={{ fontSize: 13 }}>
                      {confidence >= 0.75
                        ? 'Vollständige Datenbasis – Empfehlung sehr zuverlässig'
                        : confidence >= 0.55
                        ? 'Gute Datenbasis – Verkaufsdaten würden Präzision erhöhen'
                        : 'Lückenhafte Daten – Kostendaten und Verkäufe hinterlegen'}
                    </s-paragraph>
                  </s-stack>

                  {/* KI-Erklärung */}
                  {!aiExplanation && !aiLoading && (
                    <s-button
                      variant="plain"
                      size="slim"
                      onClick={handleAiExplain}
                    >
                      ✨ KI-Erklärung anzeigen
                    </s-button>
                  )}
                  {aiLoading && (
                    <s-stack direction="inline" gap="2" style={{ alignItems: 'center' }}>
                      <s-spinner size="small" />
                      <s-paragraph tone="subdued" style={{ fontSize: 13 }}>
                        KI analysiert...
                      </s-paragraph>
                    </s-stack>
                  )}
                  {aiError && (
                    <s-paragraph tone="critical" style={{ fontSize: 13 }}>
                      KI-Erklärung nicht verfügbar – bitte versuche es später erneut.
                    </s-paragraph>
                  )}
                  {aiExplanation && (
                    <div
                      className="vlerafy-ai-container"
                      style={{ marginTop: 12, borderRadius: 'var(--v-radius-md)', padding: 16 }}
                    >
                      <s-stack direction="block" gap="3">
                        <s-stack direction="inline" gap="2" style={{ alignItems: 'center' }}>
                          <div
                            style={{
                              width: 28,
                              height: 28,
                              borderRadius: 'var(--v-radius-sm)',
                              background: 'var(--v-indigo-600)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: 'var(--v-white)',
                            }}
                          >
                            ✨
                          </div>
                          <s-text fontWeight="600" style={{ fontSize: 13 }}>
                            KI-Analyse
                          </s-text>
                          <s-badge tone="info">{aiExplanation.confidence_text}</s-badge>
                        </s-stack>
                        <s-paragraph tone="subdued" style={{ fontSize: 13 }}>
                          {aiExplanation.explanation}
                        </s-paragraph>
                        <div
                          className="vlerafy-reasoning-block"
                          style={{ marginTop: 4 }}
                        >
                          <s-stack direction="inline" gap="2" style={{ alignItems: 'center' }}>
                            <span>💡</span>
                            <s-text fontWeight="600" style={{ fontSize: 13 }}>
                              {aiExplanation.key_reason}
                            </s-text>
                          </s-stack>
                        </div>
                        <s-stack direction="inline" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                          <s-paragraph tone="subdued" style={{ fontSize: 13 }}>
                            {aiExplanation.action_hint}
                          </s-paragraph>
                          <s-button variant="plain" size="slim" onClick={() => setAiExplanation(null)}>
                            Schließen
                          </s-button>
                        </s-stack>
                      </s-stack>
                    </div>
                  )}

                  {/* Chat UI – nur wenn KI-Erklärung angezeigt */}
                  {aiExplanation && (
                    <div className="vlerafy-ai-container" style={{ marginTop: 8 }}>
                      <div className="vlerafy-ai-header">
                        <span className="vlerafy-ai-header-title">💬 Frag die KI</span>
                        <span style={{ fontSize: 12, opacity: 0.9 }}>· Stelle Fragen zur Preisempfehlung</span>
                      </div>

                      {chatMessages.length > 0 && (
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
                            <s-stack direction="inline" gap="2" style={{ alignItems: 'center' }}>
                              <s-spinner size="small" />
                              <s-paragraph tone="subdued" style={{ fontSize: 13 }}>
                                KI denkt nach...
                              </s-paragraph>
                            </s-stack>
                          )}
                          <div ref={chatBottomRef} />
                        </div>
                      )}

                      {chatMessages.length === 0 && (
                        <div className="vlerafy-chat-input-row" style={{ flexWrap: 'wrap', gap: 8 }}>
                          {[
                            'Warum soll ich den Preis senken?',
                            'Ist die Empfehlung sicher?',
                            'Was passiert wenn ich nichts ändere?',
                          ].map((q) => (
                            <button
                              key={q}
                              type="button"
                              onClick={() => setChatInput(q)}
                              className="vlerafy-tab"
                              style={{ margin: 0 }}
                            >
                              {q}
                            </button>
                          ))}
                        </div>
                      )}

                      <div className="vlerafy-chat-input-row">
                        <input
                          value={chatInput}
                          onChange={(e) => setChatInput(e.target.value)}
                          onKeyDown={(e) =>
                            e.key === 'Enter' && !e.shiftKey && handleChatSend()
                          }
                          placeholder="Frage zur Preisempfehlung..."
                          style={{
                            flex: 1,
                            border: '1px solid var(--v-gray-200)',
                            borderRadius: 'var(--v-radius-sm)',
                            padding: '8px 12px',
                            fontSize: 13,
                            outline: 'none',
                            background: 'var(--v-gray-50)',
                            color: 'var(--v-gray-950)',
                          }}
                        />
                        <s-button
                          variant="primary"
                          onClick={handleChatSend}
                          disabled={!chatInput.trim() || chatLoading}
                        >
                          Senden
                        </s-button>
                      </div>
                    </div>
                  )}

                  <s-divider />

                  {/* 3. Warum dieser Preis? */}
                  <s-heading size="sm">Warum dieser Preis?</s-heading>
                  <s-stack direction="block" gap="3">
                    {competitorStrategy && competitorAvg != null && (
                      <div style={{ background: 'var(--v-gray-50)', borderRadius: 'var(--v-radius-md)', padding: '12px 16px', border: '1px solid var(--v-gray-200)' }}>
                        <s-stack direction="inline" gap="3" style={{ alignItems: 'flex-start' }}>
                          <div style={{ width: 36, height: 36, borderRadius: 'var(--v-radius-sm)', background: 'var(--v-indigo-50)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                            📦
                          </div>
                          <s-stack direction="block" gap="1">
                            <s-stack direction="inline" gap="2" style={{ alignItems: 'center' }}>
                              <s-text fontWeight="600" style={{ fontSize: 13 }}>Marktposition</s-text>
                              <s-badge tone="info">{`Wettbewerber Ø ${formatPrice(competitorAvg)}`}</s-badge>
                            </s-stack>
                            <s-paragraph tone="subdued" style={{ fontSize: 13 }}>
                              {currentPrice > competitorAvg
                                ? `Dein Preis liegt ${((currentPrice / competitorAvg - 1) * 100).toFixed(0)}% über dem Marktdurchschnitt. Eine Anpassung verbessert die Wettbewerbsfähigkeit.`
                                : `Dein Preis liegt ${((1 - currentPrice / competitorAvg) * 100).toFixed(0)}% unter dem Marktdurchschnitt. Preiserhöhung möglich ohne Wettbewerbsnachteil.`}
                            </s-paragraph>
                          </s-stack>
                        </s-stack>
                      </div>
                    )}
                    {breakEven != null && (
                      <div style={{ background: 'var(--v-gray-50)', borderRadius: 'var(--v-radius-md)', padding: '12px 16px', border: '1px solid var(--v-gray-200)' }}>
                        <s-stack direction="inline" gap="3" style={{ alignItems: 'flex-start' }}>
                          <div style={{ width: 36, height: 36, borderRadius: 'var(--v-radius-sm)', background: marginPercent > 20 ? 'var(--v-success-bg)' : 'var(--v-critical-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                            💰
                          </div>
                          <s-stack direction="block" gap="1">
                            <s-stack direction="inline" gap="2" style={{ alignItems: 'center' }}>
                              <s-text fontWeight="600" style={{ fontSize: 13 }}>Marge & Rentabilität</s-text>
                              <s-badge tone={marginPercent > 20 ? 'success' : 'critical'}>{`${marginPercent.toFixed(1)}% Marge`}</s-badge>
                            </s-stack>
                            <s-paragraph tone="subdued" style={{ fontSize: 13 }}>
                              Break-Even bei {formatPrice(breakEven)}.
                              {recommendedPrice > breakEven
                                ? ` Empfohlener Preis sichert ${(((recommendedPrice - breakEven) / recommendedPrice) * 100).toFixed(1)}% Marge.`
                                : ' ⚠️ Empfohlener Preis liegt unter Break-Even – Schutzregel aktiv.'}
                            </s-paragraph>
                          </s-stack>
                        </s-stack>
                      </div>
                    )}
                    {inventory != null && inventory !== undefined && (
                      <div style={{ background: 'var(--v-gray-50)', borderRadius: 'var(--v-radius-md)', padding: '12px 16px', border: '1px solid var(--v-gray-200)' }}>
                        <s-stack direction="inline" gap="3" style={{ alignItems: 'flex-start' }}>
                          <div style={{ width: 36, height: 36, borderRadius: 'var(--v-radius-sm)', background: 'var(--v-warning-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                            📦
                          </div>
                          <s-stack direction="block" gap="1">
                            <s-stack direction="inline" gap="2" style={{ alignItems: 'center' }}>
                              <s-text fontWeight="600" style={{ fontSize: 13 }}>Lagerbestand</s-text>
                              <s-badge tone={inventory > 20 ? 'success' : inventory > 5 ? 'warning' : 'critical'}>{`${inventory} Stück`}</s-badge>
                            </s-stack>
                            <s-paragraph tone="subdued" style={{ fontSize: 13 }}>
                              {inventory > 50
                                ? 'Hoher Lagerbestand – kein Abverkaufsdruck, Preis kann stabil bleiben oder steigen.'
                                : inventory > 10
                                ? 'Normaler Lagerbestand – Preis basiert auf Markt und Marge.'
                                : 'Niedriger Lagerbestand – Knappheit kann höheren Preis rechtfertigen.'}
                            </s-paragraph>
                          </s-stack>
                        </s-stack>
                      </div>
                    )}
                    {confidence < 0.75 && (
                      <div style={{ background: 'var(--v-warning-bg)', borderRadius: 'var(--v-radius-md)', padding: '12px 16px', border: '1px solid var(--v-warning-muted)' }}>
                        <s-stack direction="block" gap="1">
                          <s-text fontWeight="600" style={{ fontSize: 13, color: 'var(--v-warning)' }}>💡 Empfehlung verbessern</s-text>
                          <s-paragraph tone="subdued" style={{ fontSize: 13 }}>
                            {!hasCostData && '- Kostendaten eintragen → Break-Even-Schutz aktiv\n'}
                            {sales7d === 0 && '- Erste Verkäufe abwarten → Nachfrageanalyse wird präziser\n'}
                            {!hasCompetitorData && '- Wettbewerber aktualisieren → Marktvergleich verbessert Empfehlung'}
                          </s-paragraph>
                        </s-stack>
                      </div>
                    )}
                  </s-stack>

                  <s-divider />

                  <s-heading size="md">Begründung</s-heading>
                  <s-paragraph>{reasoningText}</s-paragraph>

                  <s-stack direction="inline" gap="3">
                    <s-button variant="primary" onClick={() => applyMutation.mutate()} loading={applyMutation.isPending}>
                      Preis übernehmen ({formatPrice(recommendedPrice)})
                    </s-button>
                    <s-button variant="secondary" onClick={() => generateMutation.mutate()} loading={generateMutation.isPending}>
                      Neu analysieren
                    </s-button>
                  </s-stack>
                </>
              ) : (
                <s-stack direction="block" gap="4">
                  <s-paragraph tone="subdued">
                    Noch keine Empfehlung für dieses Produkt.
                  </s-paragraph>
                  <s-button
                    variant="primary"
                    onClick={() => generateMutation.mutate()}
                    loading={generateMutation.isPending}
                  >
                    Empfehlung generieren
                  </s-button>
                </s-stack>
              )}
            </s-stack>
          </s-section>

      <s-section style={{ marginTop: 24 }}>
        <s-stack direction="block" gap="4">
          <s-heading size="md">
            Margen-Analyse
          </s-heading>
              {margin?.has_cost_data ? (
                <>
                  <s-grid columns="2" gap="4" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
                    <s-stack direction="block" gap="1">
                      <s-paragraph tone="subdued">Verkaufspreis</s-paragraph>
                      <s-heading size="lg">€{margin.selling_price}</s-heading>
                    </s-stack>
                    <s-stack direction="block" gap="1">
                      <s-paragraph tone="subdued">Nettoerlös</s-paragraph>
                      <s-heading size="lg">€{margin.net_revenue.toFixed(2)}</s-heading>
                    </s-stack>
                  </s-grid>

                  <s-heading size="md">Kostenaufstellung</s-heading>
                  <s-list>
                    <ul style={{ margin: 0, paddingLeft: 20, color: 'var(--v-gray-700)' }}>
                      <li>Einkauf: €{margin.costs.purchase.toFixed(2)}</li>
                      <li>Versand: €{margin.costs.shipping.toFixed(2)}</li>
                      <li>Verpackung: €{margin.costs.packaging.toFixed(2)}</li>
                      <li>Zahlungsgebühr ({margin.payment_provider}): €{margin.costs.payment_fee.toFixed(2)}</li>
                      <li><strong>Gesamt: €{margin.costs.total_variable.toFixed(2)}</strong></li>
                    </ul>
                  </s-list>

                  <s-text style={{ fontSize: 18, fontWeight: 600 }}>
                    Deckungsbeitrag: €{margin.margin.euro.toFixed(2)} ({margin.margin.percent.toFixed(1)}%)
                  </s-text>
                  <div className="vlerafy-progress">
                    <div className="vlerafy-progress-bar" style={{ width: `${Math.min(100, margin.margin.percent)}%` }} />
                  </div>

                  <s-heading size="md">Preis-Benchmarks</s-heading>
                  <ul style={{ margin: 0, paddingLeft: 20, color: 'var(--v-gray-700)' }}>
                    <li>Break-Even: €{margin.break_even_price.toFixed(2)}{' '}
                      <s-badge tone={margin.is_above_break_even ? 'success' : 'critical'}>
                        {margin.is_above_break_even ? '✓ OK' : '✗ Unter Break-Even'}
                      </s-badge>
                    </li>
                    <li>Mindestpreis (20% Marge): €{margin.recommended_min_price.toFixed(2)}{' '}
                      <s-badge tone={margin.is_above_min_margin ? 'success' : 'warning'}>
                        {margin.is_above_min_margin ? '✓ OK' : '⚠ Unter Mindestmarge'}
                      </s-badge>
                    </li>
                    <li>MwSt: {margin.vat_rate}% ({margin.country_code})</li>
                  </ul>

                  <s-divider />

                  <s-heading size="md">Rentabilitäts-Übersicht</s-heading>
                  <s-grid columns="4" gap="3" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                    {[
                      { label: 'Nettoumsatz', value: formatPrice(margin.net_revenue), hint: 'Nach MwSt-Abzug' },
                      { label: 'Rohgewinn', value: formatPrice(margin.margin.euro), tone: margin.margin.euro > 0 ? 'success' : 'critical' },
                      { label: 'Marge', value: margin.margin.percent.toFixed(1) + '%', tone: margin.margin.percent >= 20 ? 'success' : 'critical' },
                      { label: 'ROI', value: (margin.costs.total_variable > 0 ? (margin.margin.euro / margin.costs.total_variable) * 100 : 0).toFixed(0) + '%', hint: 'Return on Investment' },
                    ].map((item, i) => (
                      <s-stack key={i} direction="block" gap="1">
                        <s-paragraph tone="subdued" style={{ fontSize: 13 }}>{item.label}</s-paragraph>
                        <s-text style={{ fontSize: 18, fontWeight: 600, color: (item as { tone?: string }).tone === 'success' ? 'var(--v-success)' : (item as { tone?: string }).tone === 'critical' ? 'var(--v-critical)' : undefined }}>
                          {item.value}
                        </s-text>
                        {(item as { hint?: string }).hint && <s-paragraph tone="subdued" style={{ fontSize: 12 }}>{(item as { hint?: string }).hint}</s-paragraph>}
                      </s-stack>
                    ))}
                  </s-grid>

                  <s-heading size="md">Preis-Szenarien</s-heading>
                  <s-paragraph tone="subdued" style={{ fontSize: 13 }}>Was passiert bei verschiedenen Preisen?</s-paragraph>
                  <s-stack direction="block" gap="1">
                    {[
                      { label: 'Break-Even', price: margin.break_even_price, margin: 0 },
                      { label: 'Ziel-Marge (20%)', price: margin.recommended_min_price, margin: 20 },
                      { label: 'Aktueller Preis', price: margin.selling_price, margin: margin.margin.percent, highlight: true },
                      ...(recommendation ? [{ label: 'Empfohlener Preis', price: recommendation.recommended_price, margin: ((recommendation.recommended_price / (1 + (margin.vat_rate || 19) / 100) - margin.costs.total_variable) / (recommendation.recommended_price / (1 + (margin.vat_rate || 19) / 100))) * 100 }] : []),
                      ...(competitors?.competitor_avg ? [{ label: 'Wettbewerber Ø', price: competitors.competitor_avg, margin: ((competitors.competitor_avg / (1 + (margin.vat_rate || 19) / 100) - margin.costs.total_variable) / (competitors.competitor_avg / (1 + (margin.vat_rate || 19) / 100))) * 100 }] : []),
                    ].map((scenario, i) => (
                      <div key={i} style={{ padding: '8px 12px', background: (scenario as { highlight?: boolean }).highlight ? 'var(--v-indigo-50)' : 'transparent', borderRadius: 6 }}>
                        <s-stack direction="inline" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                          <s-paragraph style={{ fontSize: 13 }}>{(scenario as { label: string }).label}</s-paragraph>
                          <s-text fontWeight="600" style={{ fontSize: 13 }}>{formatPrice((scenario as { price: number }).price)}</s-text>
                          <s-badge tone={((scenario as { margin: number }).margin >= 20 ? 'success' : (scenario as { margin: number }).margin >= 0 ? 'warning' : 'critical') as 'success' | 'warning' | 'critical'}>
                            {(scenario as { margin: number }).margin.toFixed(1)}% Marge
                          </s-badge>
                        </s-stack>
                      </div>
                    ))}
                  </s-stack>

                  <s-button onClick={() => setShowCostForm(true)}>
                    Kosten bearbeiten
                  </s-button>
                </>
              ) : (
                <s-banner tone="info" title="Keine Kostendaten">
                  Füge Kostendaten hinzu um die Marge zu berechnen.
                </s-banner>
              )}

              {(showCostForm || !margin?.has_cost_data) && (
                <s-section style={{ marginTop: 16 }}>
                  <s-stack direction="block" gap="4">
                    <s-heading size="md">Kostendaten eingeben</s-heading>
                    <s-stack direction="block" gap="2">
                      <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--v-gray-700)' }}>Kategorie (lädt Standardwerte)</label>
                      <select
                        value={costForm.category}
                        onChange={(e) => loadCategoryDefaults(e.target.value)}
                        style={{
                          padding: '8px 12px',
                          border: '1px solid var(--v-gray-200)',
                          borderRadius: 'var(--v-radius-sm)',
                          fontSize: 13,
                          background: 'var(--v-white)',
                          color: 'var(--v-gray-950)',
                        }}
                      >
                        {CATEGORIES.map((c) => (
                          <option key={c.value} value={c.value}>{c.label}</option>
                        ))}
                      </select>
                    </s-stack>
                    <s-text-field
                      label="Einkaufspreis (€)"
                      type="number"
                      value={costForm.purchase_cost}
                      onChange={(e) => setCostForm((p) => ({ ...p, purchase_cost: (e.target as HTMLInputElement).value }))}
                    />
                    <s-text-field
                      label="Versandkosten (€)"
                      type="number"
                      value={costForm.shipping_cost}
                      onChange={(e) => setCostForm((p) => ({ ...p, shipping_cost: (e.target as HTMLInputElement).value }))}
                    />
                    <s-text-field
                      label="Verpackungskosten (€)"
                      type="number"
                      value={costForm.packaging_cost}
                      onChange={(e) => setCostForm((p) => ({ ...p, packaging_cost: (e.target as HTMLInputElement).value }))}
                    />
                    <s-stack direction="block" gap="2">
                      <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--v-gray-700)' }}>Zahlungsanbieter</label>
                      <select
                        value={costForm.payment_provider}
                        onChange={(e) => setCostForm((p) => ({ ...p, payment_provider: e.target.value }))}
                        style={{
                          padding: '8px 12px',
                          border: '1px solid var(--v-gray-200)',
                          borderRadius: 'var(--v-radius-sm)',
                          fontSize: 13,
                          background: 'var(--v-white)',
                          color: 'var(--v-gray-950)',
                        }}
                      >
                        {PAYMENT_PROVIDERS.map((c) => (
                          <option key={c.value} value={c.value}>{c.label}</option>
                        ))}
                      </select>
                    </s-stack>
                    <s-stack direction="inline" gap="3">
                      <s-button variant="primary" onClick={() => saveCostsMutation.mutate()} loading={saveCostsMutation.isPending}>
                        Speichern & Marge berechnen
                      </s-button>
                      {showCostForm && (
                        <s-button variant="plain" onClick={() => setShowCostForm(false)}>
                          Abbrechen
                        </s-button>
                      )}
                    </s-stack>
                  </s-stack>
                </s-section>
              )}
            </s-stack>
          </s-section>

      <s-section style={{ marginTop: 24 }}>
        <s-stack direction="block" gap="4">
          <s-heading size="md">Wettbewerbsanalyse</s-heading>
          {compLoading ? (
            <div className="vlerafy-skeleton vlerafy-skeleton-text" style={{ height: 100 }} />
              ) : competitors?.has_data ? (
                <>
                  <s-grid columns="3" gap="4" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
                    <s-stack direction="block" gap="1">
                      <s-paragraph tone="subdued">Dein Preis</s-paragraph>
                      <s-heading size="lg">{formatPrice(competitors.current_price)}</s-heading>
                    </s-stack>
                    <s-stack direction="block" gap="1">
                      <s-paragraph tone="subdued">Marktdurchschnitt</s-paragraph>
                      <s-heading size="lg">{formatPrice(competitors.competitor_avg ?? 0)}</s-heading>
                      <s-paragraph tone="subdued" style={{ fontSize: 12 }}>{competitors.competitor_count} Anbieter</s-paragraph>
                    </s-stack>
                    <s-stack direction="block" gap="1">
                      <s-paragraph tone="subdued">Preisspanne</s-paragraph>
                      <s-heading size="lg">
                        {formatPrice(competitors.competitor_min ?? 0)} – {formatPrice(competitors.competitor_max ?? 0)}
                      </s-heading>
                    </s-stack>
                  </s-grid>

                  {/* Marktposition visuell */}
                  {competitors.competitor_min != null && competitors.competitor_max != null && competitors.competitor_avg != null && (
                    <div className="vlerafy-market-position" style={{ marginTop: 16 }}>
                      <s-stack direction="block" gap="3">
                        <s-heading size="md">Marktposition</s-heading>
                        <div className="vlerafy-market-bar" style={{ position: 'relative', height: 60 }}>
                          <div style={{ position: 'absolute', top: 24, left: 0, right: 0, height: 8, background: 'var(--v-gray-200)', borderRadius: 4 }} />
                          {(() => {
                            const minP = competitors.competitor_min!;
                            const maxP = competitors.competitor_max!;
                            const range = maxP - minP || 1;
                            const toPercent = (p: number) => Math.min(100, Math.max(0, ((p - minP) / range) * 100));
                            const avgLeft = toPercent(competitors.competitor_avg!);
                            const myLeft = toPercent(myPrice);
                            return (
                              <>
                                <div style={{ position: 'absolute', top: 24, height: 8, left: 0, width: '100%', background: 'linear-gradient(90deg, var(--v-success-muted), var(--v-success))', borderRadius: 4, opacity: 0.6 }} />
                                <div style={{ position: 'absolute', left: `${avgLeft}%`, top: 16, transform: 'translateX(-50%)', width: 4, height: 24, background: 'var(--v-success)', borderRadius: 2 }} title={`Marktdurchschnitt: ${formatPrice(competitors.competitor_avg!)}`} />
                                <div className="vlerafy-market-indicator" style={{ left: `${myLeft}%` }} title={`Dein Preis: ${formatPrice(myPrice)}`} />
                              </>
                            );
                          })()}
                        </div>
                        <s-stack direction="inline" gap="4" style={{ flexWrap: 'wrap' }}>
                          <s-stack direction="inline" gap="1" style={{ alignItems: 'center' }}>
                            <div style={{ width: 12, height: 12, borderRadius: '50%', background: 'var(--v-navy-700)' }} />
                            <s-paragraph style={{ fontSize: 13 }}>Dein Preis {formatPrice(myPrice)}</s-paragraph>
                          </s-stack>
                          <s-stack direction="inline" gap="1" style={{ alignItems: 'center' }}>
                            <div style={{ width: 12, height: 4, background: 'var(--v-success)', marginTop: 4, borderRadius: 2 }} />
                            <s-paragraph style={{ fontSize: 13 }}>Markt Ø {formatPrice(competitors.competitor_avg!)}</s-paragraph>
                          </s-stack>
                        </s-stack>
                        <s-banner tone={(() => {
                          const avg = competitors.competitor_avg ?? 0;
                          if (avg <= 0) return 'info';
                          return myPrice > avg * 1.1 ? 'warning' : myPrice < avg * 0.9 ? 'info' : 'success';
                        })()}
                        title=""
                      >
                        {(() => {
                          const avg = competitors.competitor_avg ?? 0;
                          if (avg <= 0) return 'Kein Marktdurchschnitt verfügbar.';
                          if (myPrice > avg * 1.1) return `Dein Preis liegt ${((myPrice / avg - 1) * 100).toFixed(0)}% über dem Marktdurchschnitt – prüfe ob dein Produkt diesen Aufpreis rechtfertigt.`;
                          if (myPrice < avg * 0.9) return `Dein Preis liegt ${((1 - myPrice / avg) * 100).toFixed(0)}% unter dem Marktdurchschnitt – Potenzial für Preiserhöhung vorhanden.`;
                          return 'Dein Preis liegt im Marktdurchschnitt – gute Wettbewerbsposition.';
                        })()}
                      </s-banner>
                      </s-stack>
                    </div>
                  )}

                  <s-table>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--v-gray-200)' }}>
                          <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: 13, color: 'var(--v-gray-500)', fontWeight: 600 }}>Anbieter</th>
                          <th style={{ padding: '12px 16px', textAlign: 'right', fontSize: 13, color: 'var(--v-gray-500)', fontWeight: 600 }}>Preis</th>
                          <th style={{ padding: '12px 16px', textAlign: 'right', fontSize: 13, color: 'var(--v-gray-500)', fontWeight: 600 }}>Abweichung</th>
                          <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: 13, color: 'var(--v-gray-500)', fontWeight: 600 }}>Quelle</th>
                          <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: 13, color: 'var(--v-gray-500)', fontWeight: 600 }}>Letzte Abfrage</th>
                        </tr>
                      </thead>
                      <tbody>
                        {compDisplay.map((c, i) => (
                          <tr key={c.url || i} className="vlerafy-table-row" style={{ borderBottom: '1px solid var(--v-gray-100)' }}>
                            <td style={{ padding: '12px 16px', fontSize: 14, color: 'var(--v-gray-950)' }}>#{i + 1} {c.title}</td>
                            <td style={{ padding: '12px 16px', fontSize: 14, textAlign: 'right', color: 'var(--v-gray-950)' }}>{formatPrice(c.price)}</td>
                            <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                              <s-badge tone={(c.deviation > 10 ? 'critical' : c.deviation < -10 ? 'success' : 'warning') as 'critical' | 'success' | 'warning'}>
                                {`${c.deviation > 0 ? '▲' : '▼'} ${Math.abs(c.deviation).toFixed(1)}%`}
                              </s-badge>
                            </td>
                            <td style={{ padding: '12px 16px', fontSize: 14, color: 'var(--v-gray-950)' }}>{c.source}</td>
                            <td style={{ padding: '12px 16px', fontSize: 13, color: 'var(--v-gray-500)' }}>
                              {c.scraped_at ? new Date(c.scraped_at).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' }) : '–'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </s-table>

                  {compDisplay.length > 0 && (
                    <s-section style={{ marginTop: 16 }}>
                      <s-stack direction="block" gap="1">
                        <s-heading size="sm">Handlungsempfehlung</s-heading>
                        <s-paragraph tone="subdued" style={{ fontSize: 13 }}>
                          {cheapestBelowUs && cheapestCompetitor
                            ? `${cheapestCompetitor.title} bietet ${formatPrice(cheapestCompetitor.price)} an – ${Math.abs(cheapestDeviation).toFixed(0)}% günstiger als du. Prüfe ob Qualitätsunterschiede den Preisabstand rechtfertigen.`
                            : 'Du bist einer der günstigsten Anbieter. Preiserhöhung auf Ø ' + formatPrice(competitors.competitor_avg ?? 0) + ' möglich ohne Wettbewerbsnachteil.'}
                        </s-paragraph>
                      </s-stack>
                    </s-section>
                  )}
                </>
              ) : (
                <s-paragraph tone="subdued">
                  Noch keine Wettbewerbsdaten. Suche starten um Konkurrenten zu finden.
                </s-paragraph>
              )}

              <s-button
                onClick={() => competitorSearchMutation.mutate()}
                loading={competitorSearchMutation.isPending}
                variant="primary"
              >
                {competitors?.has_data ? 'Wettbewerber aktualisieren' : 'Wettbewerber suchen (Serper)'}
              </s-button>
            </s-stack>
          </s-section>
        </div>

        <div>
          <PreisverlaufChart
            data={chartData}
            title="Preisentwicklung"
            subtitle="Letzte 30 Tage"
          />
        </div>
      </div>
    </div>
  );
}
