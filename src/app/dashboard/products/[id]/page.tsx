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
  { label: 'Stripe (2.9% + 0.30 €)', value: 'stripe' },
  { label: 'PayPal (2.49% + 0.35 €)', value: 'paypal' },
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
    const text = obj.text ?? obj.explanation ?? obj.summary ?? obj.reasoning;
    if (typeof text === 'string') return text;
    if (obj.strategies && typeof obj.strategies === 'object') {
      const strats = obj.strategies as Record<string, unknown>;
      const first = Object.values(strats)[0];
      if (first && typeof first === 'object') {
        const s = first as Record<string, unknown>;
        if (typeof s.reasoning === 'string') return s.reasoning;
      }
    }
  }
  return null;
}

function ArrowRight() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      <path d="M4 2l4 4-4 4" />
    </svg>
  );
}

function formatEuro(v: number): string {
  return v.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
}

export default function ProductDetailPage() {
  const { id } = useParams();
  const productId = Number(id);
  const qc = useQueryClient();
  const suffix = useShopSuffix();

  type PaymentProvider = 'stripe' | 'paypal' | 'klarna' | 'custom';
  const initialCostForm: {
    purchase_cost: string; shipping_cost: string; packaging_cost: string;
    payment_provider: PaymentProvider; payment_fee_percentage: string; payment_fee_fixed: string;
    country_code: string; category: string;
  } = {
    purchase_cost: '', shipping_cost: '', packaging_cost: '',
    payment_provider: 'stripe', payment_fee_percentage: '2.9', payment_fee_fixed: '0.30',
    country_code: 'DE', category: 'fashion',
  };
  const [costForm, setCostForm] = useState(initialCostForm);
  const [costFormDirty, setCostFormDirty] = useState(false);
  const [aiExplanation, setAiExplanation] = useState<{
    explanation: string; key_reason: string; confidence_text: string; action_hint: string;
  } | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [, setAiError] = useState(false);
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  const { data: products = [] } = useQuery({ queryKey: ['products'], queryFn: () => fetchProducts() });
  const product = products.find((p) => p.id === productId);

  const { data: recommendation, isLoading: recLoading } = useQuery<Recommendation | null>({
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
  const chartData = marginHistory?.history?.map((h) => ({
    date: new Date(h.date).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' }),
    price: h.selling_price,
  })) ?? [];

  const { data: margin } = useQuery({
    queryKey: ['margin', product?.shopify_product_id, recommendation?.recommended_price ?? product?.price],
    queryFn: () => calculateMargin(product!.shopify_product_id, recommendation?.recommended_price ?? product!.price ?? 0),
    enabled: !!existingCosts && !!product?.shopify_product_id,
  });

  const generateMutation = useMutation({
    mutationFn: () => generateRecommendation(productId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['recommendation', productId] }); showToast('Empfehlung generiert!', { duration: 3000 }); },
    onError: () => showToast('Fehler beim Generieren', { isError: true }),
  });

  const applyMutation = useMutation({
    mutationFn: async () => {
      if (!recommendation) throw new Error('Keine Empfehlung');
      await applyPrice(productId, recommendation.recommended_price, recommendation.id);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['products'] }); qc.invalidateQueries({ queryKey: ['dashboard-stats'] }); showToast('Preis erfolgreich übernommen!', { duration: 3000 }); },
    onError: (err) => showToast(err.message || 'Fehler beim Übernehmen', { isError: true }),
  });

  const saveCostsMutation = useMutation({
    mutationFn: () => saveProductCosts({
      product_id: product!.shopify_product_id,
      purchase_cost: parseFloat(costForm.purchase_cost), shipping_cost: parseFloat(costForm.shipping_cost),
      packaging_cost: parseFloat(costForm.packaging_cost), payment_provider: costForm.payment_provider,
      payment_fee_percentage: parseFloat(costForm.payment_fee_percentage), payment_fee_fixed: parseFloat(costForm.payment_fee_fixed),
      country_code: costForm.country_code, category: costForm.category,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['costs', product?.shopify_product_id] }); qc.invalidateQueries({ queryKey: ['margin'] }); setCostFormDirty(false); showToast('Kostendaten gespeichert!', { duration: 3000 }); },
    onError: () => showToast('Fehler beim Speichern', { isError: true }),
  });

  const competitorSearchMutation = useMutation({
    mutationFn: () => searchCompetitors(productId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['competitors', productId] }); showToast('Wettbewerber aktualisiert!', { duration: 3000 }); },
    onError: () => showToast('Competitor Search fehlgeschlagen', { isError: true }),
  });

  const handleCostDiscard = () => {
    if (existingCosts) {
      setCostForm({
        purchase_cost: String(existingCosts.purchase_cost), shipping_cost: String(existingCosts.shipping_cost),
        packaging_cost: String(existingCosts.packaging_cost), payment_provider: (existingCosts.payment_provider || 'stripe') as PaymentProvider,
        payment_fee_percentage: String(existingCosts.payment_fee_percentage), payment_fee_fixed: String(existingCosts.payment_fee_fixed),
        country_code: existingCosts.country_code, category: existingCosts.category ?? 'fashion',
      });
    } else { setCostForm({ ...initialCostForm }); }
    setCostFormDirty(false);
  };

  const loadCategoryDefaults = async (category: string) => {
    const defaults = await getCategoryDefaults(category);
    setCostFormDirty(true);
    setCostForm((prev) => ({ ...prev, category, shipping_cost: String(defaults.shipping_estimate), packaging_cost: String(defaults.packaging_estimate) }));
  };

  const handleAiExplain = async () => {
    if (!recommendation) return;
    setAiLoading(true); setAiError(false);
    try {
      const result = await explainPrice({
        current_price: recommendation.current_price, recommended_price: recommendation.recommended_price,
        confidence: recommendation.confidence ?? 0, price_change_pct: recommendation.price_change_pct ?? 0,
        strategies: recommendation.reasoning_object?.strategies as Record<string, unknown> | undefined,
        competitor_avg: recommendation.competitor_avg_price, break_even: margin?.break_even_price,
        inventory: product?.inventory ?? recommendation?.days_of_stock ?? undefined,
        product_title: product?.title, currency: 'EUR',
      });
      setAiExplanation(result);
    } catch { setAiError(true); } finally { setAiLoading(false); }
  };

  const handleChatSend = async () => {
    const msg = chatInput.trim();
    if (!msg || chatLoading) return;
    const newMessages = [...chatMessages, { role: 'user' as const, content: msg }];
    setChatMessages(newMessages); setChatInput(''); setChatLoading(true);
    try {
      const result = await chatWithAI({
        message: msg, product_title: product?.title, current_price: recommendation?.current_price,
        recommended_price: recommendation?.recommended_price, confidence: recommendation?.confidence,
        competitor_avg: recommendation?.competitor_avg_price, break_even: margin?.break_even_price,
        history: chatMessages.slice(-6),
      });
      setChatMessages([...newMessages, { role: 'assistant', content: result.reply }]);
    } catch {
      setChatMessages([...newMessages, { role: 'assistant', content: 'Tut mir leid, ich konnte deine Frage gerade nicht beantworten.' }]);
    } finally { setChatLoading(false); setTimeout(() => chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100); }
  };

  if (!product) {
    return (
      <s-page title="Produkt laden…" back-action={JSON.stringify({ content: 'Produkte', url: `/dashboard/products${suffix}` })}>
        <div className="piq-dashboard">
          <div className="piq-detail-skeleton"><s-spinner size="small" /></div>
        </div>
      </s-page>
    );
  }

  const currentPrice = product?.price ?? recommendation?.current_price ?? 0;
  const recommendedPrice = recommendation?.recommended_price ?? 0;
  const diff = recommendedPrice - currentPrice;
  const diffPct = currentPrice > 0 ? (diff / currentPrice) * 100 : 0;
  const confidence = recommendation?.confidence ?? 0;
  const confidencePct = Math.round(confidence * 100);

  const compList = competitors?.competitors ?? [];
  const myPrice = competitors?.current_price ?? product?.price ?? 0;
  const compDisplay = compList.map((c: { title?: string; competitor_name?: string; price: number; source?: string; url?: string; competitor_url?: string; scraped_at?: string }) => {
    const deviation = myPrice > 0 ? ((c.price - myPrice) / myPrice) * 100 : 0;
    return { title: c.title ?? c.competitor_name ?? 'Unbekannt', price: c.price, source: c.source ?? c.competitor_name ?? '–', url: c.url ?? c.competitor_url ?? '', scraped_at: c.scraped_at, deviation };
  });
  const cheapestCompetitor = compDisplay.length > 0 ? compDisplay.reduce((a, b) => (a.price < b.price ? a : b)) : null;
  const cheapestBelowUs = cheapestCompetitor && cheapestCompetitor.price < myPrice;
  const cheapestDeviation = cheapestCompetitor && myPrice > 0 ? ((cheapestCompetitor.price - myPrice) / myPrice) * 100 : 0;

  const minPrice = competitors?.competitor_min ?? 0;
  const maxPrice = competitors?.competitor_max ?? 1;
  const range = maxPrice - minPrice || 1;
  const positionPct = Math.min(100, Math.max(0, ((myPrice - minPrice) / range) * 100));

  const competition = {
    avgPrice: competitors?.competitor_avg ?? 0, minPrice, maxPrice: competitors?.competitor_max ?? 0,
    count: competitors?.competitor_count ?? 0, positionPct,
    competitors: compDisplay.map((c) => ({
      name: c.title, price: c.price, diff: c.deviation, source: c.source,
      lastUpdated: c.scraped_at ? new Date(c.scraped_at).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' }) : '–',
    })),
    recommendation: cheapestBelowUs && cheapestCompetitor
      ? `${cheapestCompetitor.title} bietet ${formatEuro(cheapestCompetitor.price)} an – ${Math.abs(cheapestDeviation).toFixed(0)}% günstiger als du. Prüfe ob Qualitätsunterschiede den Preisabstand rechtfertigen.`
      : compDisplay.length > 0 ? `Du bist einer der günstigsten Anbieter. Preiserhöhung auf Ø ${formatEuro(competitors?.competitor_avg ?? 0)} möglich.` : null,
  };

  const reasoningDisplay = extractReasoningText(recommendation?.reasoning);

  const purchaseCost = parseFloat(costForm.purchase_cost) || 0;
  const shippingCost = parseFloat(costForm.shipping_cost) || 0;
  const packagingCost = parseFloat(costForm.packaging_cost) || 0;
  const totalCost = purchaseCost + shippingCost + packagingCost;
  const sellingPrice = recommendedPrice > 0 ? recommendedPrice : currentPrice;
  const grossMargin = sellingPrice - totalCost;
  const grossMarginPct = sellingPrice > 0 ? (grossMargin / sellingPrice) * 100 : 0;

  const marginFromApi = margin;
  const breakEven = marginFromApi?.break_even_price ?? totalCost;
  const netMargin = marginFromApi?.margin?.euro ?? grossMargin;
  const netMarginPct = marginFromApi?.margin?.percent ?? grossMarginPct;

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
        <div className="piq-dashboard">

          {/* ══ Action Bar ══ */}
          <div className="piq-detail-actions">
            <button className="piq-cta piq-cta--secondary" onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}>
              {generateMutation.isPending ? 'Analysiert…' : 'Neu analysieren'}
            </button>
            {recommendation && (
              <button className="piq-cta piq-cta--primary" onClick={() => applyMutation.mutate()} disabled={applyMutation.isPending}>
                {applyMutation.isPending ? 'Wird übernommen…' : `Preis übernehmen (${formatEuro(recommendedPrice)})`}
              </button>
            )}
          </div>

          {/* ══ Inventory Warning ══ */}
          {(product.inventory ?? 0) === 0 && (
            <s-banner tone="warning">Kein Lagerbestand – Knappheit kann einen höheren Preis rechtfertigen.</s-banner>
          )}

          {/* ══ Main Grid ══ */}
          <div className="piq-detail-grid">

            {/* ── LEFT COLUMN ── */}
            <div className="piq-detail-col">

              {/* Price Recommendation Card */}
              <div className="piq-detail-card piq-detail-card--rec">
                <div className="piq-detail-card-head">
                  <span className="piq-detail-section-lbl">Preisempfehlung</span>
                  {recommendation && (
                    <span className={`piq-detail-badge ${diff >= 0 ? 'piq-detail-badge--green' : 'piq-detail-badge--amber'}`}>
                      {diff >= 0 ? '▲' : '▼'} {Math.abs(diffPct).toFixed(1)}%
                    </span>
                  )}
                </div>
                <div className="piq-detail-card-body">
                  {recLoading ? (
                    <div className="piq-detail-skeleton"><s-spinner size="small" /></div>
                  ) : recommendation ? (
                    <>
                      <div className="piq-rec-prices">
                        <div className="piq-rec-current">
                          <span className="piq-rec-current-lbl">Aktuell</span>
                          <span className="piq-rec-current-val">{formatEuro(currentPrice)}</span>
                        </div>
                        <div className="piq-rec-arrow">→</div>
                        <div className="piq-rec-new">
                          <span className="piq-rec-new-lbl">Empfohlen</span>
                          <span className="piq-rec-new-val">{formatEuro(recommendedPrice)}</span>
                        </div>
                      </div>

                      <div className="piq-rec-confidence">
                        <div className="piq-rec-conf-head">
                          <span className="piq-rec-conf-lbl">Analyse-Sicherheit</span>
                          <span className="piq-rec-conf-val">{confidencePct}%</span>
                        </div>
                        <div className="piq-rec-conf-track">
                          <div className="piq-rec-conf-fill" style={{ width: `${confidencePct}%` }} />
                        </div>
                      </div>

                      {reasoningDisplay && (
                        <div className="piq-rec-reasoning">
                          <span className="piq-rec-reasoning-icon">💡</span>
                          <span className="piq-rec-reasoning-text">{reasoningDisplay}</span>
                        </div>
                      )}

                      <div className="piq-rec-btns">
                        <button className="piq-cta piq-cta--primary" onClick={() => applyMutation.mutate()} disabled={applyMutation.isPending}>
                          Preis übernehmen <ArrowRight />
                        </button>
                        <button className="piq-cta piq-cta--secondary" onClick={handleAiExplain} disabled={aiLoading}>
                          {aiLoading ? 'Analysiert…' : 'Warum dieser Preis?'}
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className="piq-rec-empty">
                      <div className="piq-rec-empty-text">Noch keine Empfehlung für dieses Produkt.</div>
                      <button className="piq-cta piq-cta--primary" onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}>
                        {generateMutation.isPending ? 'Wird generiert…' : 'Empfehlung generieren'}
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Margin Analysis Card */}
              <div className="piq-detail-card">
                <div className="piq-detail-card-head">
                  <span className="piq-detail-section-lbl">Margen-Analyse</span>
                  {totalCost > 0 && (
                    <span className={`piq-detail-badge ${netMarginPct >= 30 ? 'piq-detail-badge--green' : netMarginPct >= 15 ? 'piq-detail-badge--amber' : 'piq-detail-badge--red'}`}>
                      Marge: {netMarginPct.toFixed(1)}%
                    </span>
                  )}
                </div>
                <div className="piq-detail-card-body">
                  {totalCost > 0 ? (
                    <div className="piq-margin-grid">
                      <div className="piq-margin-item">
                        <span className="piq-margin-lbl">Verkaufspreis</span>
                        <span className="piq-margin-val">{formatEuro(sellingPrice)}</span>
                      </div>
                      <div className="piq-margin-item">
                        <span className="piq-margin-lbl">Einkauf</span>
                        <span className="piq-margin-val piq-margin-val--cost">−{formatEuro(purchaseCost)}</span>
                      </div>
                      <div className="piq-margin-item">
                        <span className="piq-margin-lbl">Versand</span>
                        <span className="piq-margin-val piq-margin-val--cost">−{formatEuro(shippingCost)}</span>
                      </div>
                      <div className="piq-margin-item">
                        <span className="piq-margin-lbl">Verpackung</span>
                        <span className="piq-margin-val piq-margin-val--cost">−{formatEuro(packagingCost)}</span>
                      </div>
                      <div className="piq-margin-divider" />
                      <div className="piq-margin-item piq-margin-item--total">
                        <span className="piq-margin-lbl">Netto-Marge</span>
                        <span className={`piq-margin-val piq-margin-val--${netMargin >= 0 ? 'profit' : 'loss'}`}>
                          {netMargin >= 0 ? '+' : ''}{formatEuro(netMargin)}
                        </span>
                      </div>
                      {breakEven > 0 && (
                        <div className="piq-margin-item">
                          <span className="piq-margin-lbl">Break-Even</span>
                          <span className="piq-margin-val">{formatEuro(breakEven)}</span>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="piq-margin-empty">
                      <span className="piq-margin-empty-text">Hinterlege Kosten um die Marge zu berechnen.</span>
                    </div>
                  )}

                  <div className="piq-margin-form">
                    <div className="piq-margin-form-row">
                      <div className="piq-margin-form-field">
                        <s-select
                          label="Kategorie"
                          value={costForm.category}
                          options={JSON.stringify(CATEGORIES.map(c => ({ label: c.label, value: c.value })))}
                          // eslint-disable-next-line @typescript-eslint/no-explicit-any
                          onChange={(e: any) => loadCategoryDefaults(e?.target?.value ?? e?.detail?.value ?? '')}
                        />
                      </div>
                      <div className="piq-margin-form-field">
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
                    </div>
                    <div className="piq-margin-form-row">
                      <div className="piq-margin-form-field">
                        <s-text-field
                          label="Einkaufspreis (€)"
                          type="number"
                          value={costForm.purchase_cost}
                          // eslint-disable-next-line @typescript-eslint/no-explicit-any
                          onChange={(e: any) => { setCostFormDirty(true); setCostForm((p) => ({ ...p, purchase_cost: e?.target?.value ?? e?.detail?.value ?? '' })); }}
                        />
                      </div>
                      <div className="piq-margin-form-field">
                        <s-text-field
                          label="Versandkosten (€)"
                          type="number"
                          value={costForm.shipping_cost}
                          // eslint-disable-next-line @typescript-eslint/no-explicit-any
                          onChange={(e: any) => { setCostFormDirty(true); setCostForm((p) => ({ ...p, shipping_cost: e?.target?.value ?? e?.detail?.value ?? '' })); }}
                        />
                      </div>
                      <div className="piq-margin-form-field">
                        <s-text-field
                          label="Verpackung (€)"
                          type="number"
                          value={costForm.packaging_cost}
                          // eslint-disable-next-line @typescript-eslint/no-explicit-any
                          onChange={(e: any) => { setCostFormDirty(true); setCostForm((p) => ({ ...p, packaging_cost: e?.target?.value ?? e?.detail?.value ?? '' })); }}
                        />
                      </div>
                    </div>
                    {costFormDirty && (
                      <div className="piq-margin-form-actions">
                        <button className="piq-cta piq-cta--primary piq-cta--sm" onClick={() => saveCostsMutation.mutate()} disabled={saveCostsMutation.isPending}>
                          {saveCostsMutation.isPending ? 'Speichert…' : 'Kosten speichern'}
                        </button>
                        <button className="piq-cta piq-cta--secondary piq-cta--sm" onClick={handleCostDiscard}>
                          Verwerfen
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Competition Analysis Card */}
              <div className="piq-detail-card">
                <div className="piq-detail-card-head">
                  <span className="piq-detail-section-lbl">Wettbewerbsanalyse</span>
                  {competition.count > 0 && (
                    <span className="piq-detail-badge piq-detail-badge--indigo">{competition.count} Anbieter</span>
                  )}
                </div>
                <div className="piq-detail-card-body">
                  {compLoading ? (
                    <div className="piq-detail-skeleton"><s-spinner size="small" /></div>
                  ) : competitors?.has_data ? (
                    <>
                      <div className="piq-comp-stats">
                        <div className="piq-comp-stat">
                          <span className="piq-comp-stat-lbl">Dein Preis</span>
                          <span className="piq-comp-stat-val">{formatEuro(myPrice)}</span>
                        </div>
                        <div className="piq-comp-stat">
                          <span className="piq-comp-stat-lbl">Ø Markt</span>
                          <span className="piq-comp-stat-val">{formatEuro(competition.avgPrice)}</span>
                        </div>
                        <div className="piq-comp-stat">
                          <span className="piq-comp-stat-lbl">Spanne</span>
                          <span className="piq-comp-stat-val">{formatEuro(competition.minPrice)} – {formatEuro(competition.maxPrice)}</span>
                        </div>
                      </div>

                      <div className="piq-comp-position">
                        <span className="piq-comp-pos-lbl">Deine Marktposition</span>
                        <div className="piq-comp-pos-track">
                          <div className="piq-comp-pos-dot" style={{ left: `${competition.positionPct}%` }} />
                        </div>
                        <div className="piq-comp-pos-range">
                          <span>{formatEuro(competition.minPrice)}</span>
                          <span>{formatEuro(competition.maxPrice)}</span>
                        </div>
                      </div>

                      <div className="piq-comp-table-wrap">
                        <table className="piq-table">
                          <thead>
                            <tr>
                              <th>Anbieter</th>
                              <th style={{ textAlign: 'right' }}>Preis</th>
                              <th style={{ textAlign: 'center' }}>Abweichung</th>
                              <th>Quelle</th>
                              <th>Abfrage</th>
                            </tr>
                          </thead>
                          <tbody>
                            {competition.competitors.map((c, idx) => (
                              <tr key={`${c.name}-${idx}`}>
                                <td>
                                  <span className="piq-comp-rank">#{idx + 1}</span> {c.name}
                                </td>
                                <td style={{ textAlign: 'right' }}>
                                  <span className="piq-price-current">{formatEuro(c.price)}</span>
                                </td>
                                <td style={{ textAlign: 'center' }}>
                                  <span className={`piq-comp-diff ${c.diff > 0 ? 'piq-comp-diff--up' : 'piq-comp-diff--down'}`}>
                                    {c.diff > 0 ? '▲' : '▼'} {Math.abs(c.diff).toFixed(1)}%
                                  </span>
                                </td>
                                <td><span className="piq-comp-source">{c.source}</span></td>
                                <td><span className="piq-comp-source">{c.lastUpdated}</span></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      {competition.recommendation && (
                        <div className="piq-comp-insight">
                          <span className="piq-comp-insight-icon">💡</span>
                          <span className="piq-comp-insight-text">{competition.recommendation}</span>
                        </div>
                      )}

                      <div style={{ marginTop: '16px' }}>
                        <button className="piq-cta piq-cta--secondary piq-cta--sm" onClick={() => competitorSearchMutation.mutate()} disabled={competitorSearchMutation.isPending}>
                          {competitorSearchMutation.isPending ? 'Sucht…' : 'Wettbewerber aktualisieren'}
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className="piq-comp-empty">
                      <span className="piq-comp-empty-text">Noch keine Wettbewerbsdaten vorhanden.</span>
                      <button className="piq-cta piq-cta--primary" onClick={() => competitorSearchMutation.mutate()} disabled={competitorSearchMutation.isPending}>
                        {competitorSearchMutation.isPending ? 'Sucht…' : 'Wettbewerber suchen'}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* ── RIGHT COLUMN ── */}
            <div className="piq-detail-col">

              {/* Price History */}
              <div className="piq-detail-card">
                <div className="piq-detail-card-head">
                  <span className="piq-detail-section-lbl">Preisentwicklung</span>
                  <span className="piq-detail-badge piq-detail-badge--gray">30 Tage</span>
                </div>
                <div className="piq-detail-card-body">
                  <PreisverlaufChart data={chartData} title="" subtitle="" />
                </div>
              </div>

              {/* AI Explanation */}
              {recommendation && (
                <div className="piq-detail-card piq-detail-card--ai">
                  <div className="piq-ai-head">
                    <span className="piq-ai-head-icon">✨</span>
                    <span className="piq-ai-head-title">KI-Assistent</span>
                  </div>

                  {!aiExplanation && !aiLoading && chatMessages.length === 0 && (
                    <div className="piq-ai-cta-wrap">
                      <button className="piq-cta piq-cta--secondary" onClick={handleAiExplain}>
                        KI-Erklärung laden
                      </button>
                    </div>
                  )}

                  {aiLoading && !aiExplanation && (
                    <div className="piq-ai-loading">
                      <s-spinner size="small" />
                      <span>KI analysiert…</span>
                    </div>
                  )}

                  {aiExplanation && (
                    <div className="piq-ai-explanation">
                      <div className="piq-ai-explain-text">{aiExplanation.explanation}</div>
                      <div className="piq-ai-meta">
                        <div className="piq-ai-meta-row">
                          <span className="piq-ai-meta-lbl">Hauptgrund</span>
                          <span className="piq-ai-meta-val">{aiExplanation.key_reason}</span>
                        </div>
                        <div className="piq-ai-meta-row">
                          <span className="piq-ai-meta-lbl">Sicherheit</span>
                          <span className="piq-ai-meta-val">{aiExplanation.confidence_text}</span>
                        </div>
                        <div className="piq-ai-meta-row">
                          <span className="piq-ai-meta-lbl">Empfehlung</span>
                          <span className="piq-ai-meta-val">{aiExplanation.action_hint}</span>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="piq-ai-chat">
                    {chatMessages.map((msg, i) => (
                      <div key={i} className={`piq-ai-bubble ${msg.role === 'user' ? 'piq-ai-bubble--user' : 'piq-ai-bubble--ai'}`}>
                        {msg.content}
                      </div>
                    ))}
                    {chatLoading && (
                      <div className="piq-ai-typing">
                        <s-spinner size="small" /> <span>KI denkt nach…</span>
                      </div>
                    )}
                    <div ref={chatBottomRef} />
                  </div>

                  <div className="piq-ai-input">
                    <s-text-field
                      label=""
                      placeholder="Frage zur Preisempfehlung…"
                      value={chatInput}
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      onChange={(e: any) => setChatInput(e?.target?.value ?? e?.detail?.value ?? '')}
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      onKeyDown={(e: any) => e.key === 'Enter' && handleChatSend()}
                    />
                    <button className="piq-cta piq-cta--primary piq-cta--sm" onClick={handleChatSend} disabled={!chatInput.trim() || chatLoading}>
                      Senden
                    </button>
                  </div>
                </div>
              )}

              {/* Product Info */}
              <div className="piq-detail-card">
                <div className="piq-detail-card-head">
                  <span className="piq-detail-section-lbl">Produktinfo</span>
                </div>
                <div className="piq-detail-card-body">
                  <div className="piq-info-grid">
                    <div className="piq-info-item">
                      <span className="piq-info-lbl">Lagerbestand</span>
                      <span className="piq-info-val">{product.inventory ?? 0} Stück</span>
                    </div>
                    <div className="piq-info-item">
                      <span className="piq-info-lbl">Aktueller Preis</span>
                      <span className="piq-info-val">{formatEuro(currentPrice)}</span>
                    </div>
                    {product.cost != null && product.cost > 0 && (
                      <div className="piq-info-item">
                        <span className="piq-info-lbl">Einkaufspreis</span>
                        <span className="piq-info-val">{formatEuro(product.cost)}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
      </s-page>
    </>
  );
}
