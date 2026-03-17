'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useSearchParams } from 'next/navigation';
import { useState, useEffect, useRef, useCallback } from 'react';
import {
  fetchProducts,
  getRecommendation,
  generateRecommendation,
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
  const initialCostForm = {
    purchase_cost: '', shipping_cost: '', packaging_cost: '',
    payment_provider: 'stripe' as PaymentProvider, payment_fee_percentage: '2.9', payment_fee_fixed: '0.30',
    country_code: 'DE', category: 'fashion',
  };
  const [costForm, setCostForm] = useState(initialCostForm);
  const [costFormDirty, setCostFormDirty] = useState(false);
  const [aiExplanation, setAiExplanation] = useState<{
    explanation: string; key_reason: string; confidence_text: string; action_hint: string;
  } | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Refs for Polaris Web Components (Shadow DOM needs native event binding)
  const purchaseRef = useRef<HTMLElement>(null);
  const shippingRef = useRef<HTMLElement>(null);
  const packagingRef = useRef<HTMLElement>(null);
  const categoryRef = useRef<HTMLElement>(null);
  const paymentRef = useRef<HTMLElement>(null);
  const chatFieldRef = useRef<HTMLElement>(null);

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

  const loadCategoryDefaults = useCallback(async (category: string) => {
    const defaults = await getCategoryDefaults(category);
    setCostFormDirty(true);
    setCostForm((prev) => ({ ...prev, category, shipping_cost: String(defaults.shipping_estimate), packaging_cost: String(defaults.packaging_estimate) }));
  }, []);

  useEffect(() => {
    const cleanups: Array<() => void> = [];
    const bind = (ref: React.RefObject<HTMLElement | null>, handler: (v: string) => void) => {
      const el = ref.current;
      if (!el) return;
      const cb = (e: Event) => {
        const t = e.target as HTMLInputElement;
        const v = t?.value ?? (e as CustomEvent)?.detail ?? '';
        handler(String(v));
      };
      el.addEventListener('change', cb);
      el.addEventListener('input', cb);
      cleanups.push(() => { el.removeEventListener('change', cb); el.removeEventListener('input', cb); });
    };
    bind(purchaseRef, (v) => { setCostFormDirty(true); setCostForm(p => ({ ...p, purchase_cost: v })); });
    bind(shippingRef, (v) => { setCostFormDirty(true); setCostForm(p => ({ ...p, shipping_cost: v })); });
    bind(packagingRef, (v) => { setCostFormDirty(true); setCostForm(p => ({ ...p, packaging_cost: v })); });
    bind(categoryRef, (v) => loadCategoryDefaults(v));
    bind(paymentRef, (v) => { setCostFormDirty(true); setCostForm(p => ({ ...p, payment_provider: v as PaymentProvider })); });
    bind(chatFieldRef, (v) => setChatInput(v));

    const chatEl = chatFieldRef.current;
    if (chatEl) {
      const keyHandler = (e: Event) => { if ((e as KeyboardEvent).key === 'Enter') document.getElementById('piq-chat-send')?.click(); };
      chatEl.addEventListener('keydown', keyHandler);
      cleanups.push(() => chatEl.removeEventListener('keydown', keyHandler));
    }

    return () => cleanups.forEach(fn => fn());
  }, [loadCategoryDefaults]);

  const handleAiExplain = async () => {
    if (!recommendation) return;
    setAiLoading(true);
    setAiExplanation(null);
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
    } catch {
      setAiExplanation({ explanation: 'Die KI-Erklärung konnte gerade nicht geladen werden. Bitte versuche es erneut.', key_reason: '–', confidence_text: '–', action_hint: '–' });
    } finally { setAiLoading(false); }
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
    return { title: c.title ?? c.competitor_name ?? 'Unbekannt', price: c.price, source: c.source ?? c.competitor_name ?? '–', scraped_at: c.scraped_at, deviation };
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
      ? `${cheapestCompetitor.title} bietet ${formatEuro(cheapestCompetitor.price)} an – ${Math.abs(cheapestDeviation).toFixed(0)}% günstiger als du.`
      : compDisplay.length > 0 ? `Du bist einer der günstigsten Anbieter. Preiserhöhung auf Ø ${formatEuro(competitors?.competitor_avg ?? 0)} möglich.` : null,
  };

  const purchaseCost = parseFloat(costForm.purchase_cost) || 0;
  const shippingCost = parseFloat(costForm.shipping_cost) || 0;
  const packagingCost = parseFloat(costForm.packaging_cost) || 0;
  const totalCost = purchaseCost + shippingCost + packagingCost;
  const sellingPrice = recommendedPrice > 0 ? recommendedPrice : currentPrice;
  const grossMargin = sellingPrice - totalCost;
  const grossMarginPct = sellingPrice > 0 ? (grossMargin / sellingPrice) * 100 : 0;
  const netMargin = margin?.margin?.euro ?? grossMargin;
  const netMarginPct = margin?.margin?.percent ?? grossMarginPct;
  const breakEven = margin?.break_even_price ?? totalCost;

  const barMin = Math.min(minPrice > 0 ? minPrice : Infinity, myPrice);
  const barMax = Math.max(maxPrice, myPrice);
  const barRange = barMax - barMin || 1;
  const cheapPct = minPrice > 0 ? Math.max(0, Math.min(100, ((minPrice - barMin) / barRange) * 100)) : 0;
  const avgPct = competition.avgPrice > 0 ? Math.max(0, Math.min(100, ((competition.avgPrice - barMin) / barRange) * 100)) : 50;
  const myPct = Math.max(0, Math.min(100, ((myPrice - barMin) / barRange) * 100));

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

          {(product.inventory ?? 0) === 0 && (
            <s-banner tone="warning">Kein Lagerbestand – Knappheit kann einen höheren Preis rechtfertigen.</s-banner>
          )}

          {/* ══ Preisempfehlung + KI ══ */}
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

                  <div className="piq-rec-btns">
                    <button className="piq-cta piq-cta--primary" onClick={() => applyMutation.mutate()} disabled={applyMutation.isPending}>
                      {applyMutation.isPending ? 'Wird übernommen…' : 'Preis übernehmen'} <ArrowRight />
                    </button>
                    <button className="piq-cta piq-cta--secondary" onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}>
                      {generateMutation.isPending ? 'Analysiert…' : 'Neu analysieren'}
                    </button>
                    <button className="piq-cta piq-cta--secondary" onClick={handleAiExplain} disabled={aiLoading}>
                      {aiLoading ? 'KI lädt…' : 'Warum dieser Preis? Frag die KI'}
                    </button>
                  </div>

                  {/* KI-Erklärung inline */}
                  {(aiExplanation || aiLoading || chatMessages.length > 0) && (
                    <div className="piq-rec-ai">
                      {aiLoading && !aiExplanation && (
                        <div className="piq-ai-loading">
                          <s-spinner size="small" /> <span>KI analysiert…</span>
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

                      {chatMessages.length > 0 && (
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
                      )}

                      <div className="piq-ai-input">
                        <s-text-field ref={chatFieldRef} label="" placeholder="Weitere Frage stellen…" value={chatInput} />
                        <button id="piq-chat-send" className="piq-cta piq-cta--primary piq-cta--sm" onClick={handleChatSend} disabled={!chatInput.trim() || chatLoading}>
                          Senden
                        </button>
                      </div>
                    </div>
                  )}
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

          {/* ══ Margen-Analyse ══ */}
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
              <div className="piq-margin-form">
                <div className="piq-margin-form-row">
                  <div className="piq-margin-form-field">
                    <s-text-field ref={purchaseRef} label="Einkaufspreis (€)" type="number" value={costForm.purchase_cost} placeholder="0.00" />
                  </div>
                  <div className="piq-margin-form-field">
                    <s-text-field ref={shippingRef} label="Versandkosten (€)" type="number" value={costForm.shipping_cost} placeholder="0.00" />
                  </div>
                  <div className="piq-margin-form-field">
                    <s-text-field ref={packagingRef} label="Verpackung (€)" type="number" value={costForm.packaging_cost} placeholder="0.00" />
                  </div>
                </div>
                <div className="piq-margin-form-row">
                  <div className="piq-margin-form-field">
                    <s-select ref={categoryRef} label="Kategorie" value={costForm.category} options={JSON.stringify(CATEGORIES.map(c => ({ label: c.label, value: c.value })))} />
                  </div>
                  <div className="piq-margin-form-field">
                    <s-select ref={paymentRef} label="Zahlungsanbieter" value={costForm.payment_provider} options={JSON.stringify(PAYMENT_PROVIDERS.map(c => ({ label: c.label, value: c.value })))} />
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

              {totalCost > 0 && (
                <div className="piq-margin-result">
                  <div className="piq-margin-grid">
                    <div className="piq-margin-item">
                      <span className="piq-margin-lbl">Verkaufspreis</span>
                      <span className="piq-margin-val">{formatEuro(sellingPrice)}</span>
                    </div>
                    <div className="piq-margin-item">
                      <span className="piq-margin-lbl">Gesamtkosten</span>
                      <span className="piq-margin-val piq-margin-val--cost">−{formatEuro(totalCost)}</span>
                    </div>
                    <div className="piq-margin-divider" />
                    <div className="piq-margin-item piq-margin-item--total">
                      <span className="piq-margin-lbl">Netto-Marge</span>
                      <span className={`piq-margin-val piq-margin-val--${netMargin >= 0 ? 'profit' : 'loss'}`}>
                        {netMargin >= 0 ? '+' : ''}{formatEuro(netMargin)} ({netMarginPct.toFixed(1)}%)
                      </span>
                    </div>
                    {breakEven > 0 && (
                      <div className="piq-margin-item">
                        <span className="piq-margin-lbl">Break-Even Preis</span>
                        <span className="piq-margin-val">{formatEuro(breakEven)}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ══ Wettbewerbsanalyse ══ */}
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
                      {minPrice > 0 && (
                        <div className="piq-pos-marker piq-pos-marker--cheap" style={{ left: `${cheapPct}%` }}>
                          <span className="piq-pos-marker-dot" />
                          <span className="piq-pos-marker-tip">
                            <span className="piq-pos-marker-label">Günstigster</span>
                            <span className="piq-pos-marker-price">{formatEuro(minPrice)}</span>
                          </span>
                        </div>
                      )}
                      {competition.avgPrice > 0 && (
                        <div className="piq-pos-marker piq-pos-marker--avg" style={{ left: `${avgPct}%` }}>
                          <span className="piq-pos-marker-dot" />
                          <span className="piq-pos-marker-tip">
                            <span className="piq-pos-marker-label">Ø Markt</span>
                            <span className="piq-pos-marker-price">{formatEuro(competition.avgPrice)}</span>
                          </span>
                        </div>
                      )}
                      <div className="piq-pos-marker piq-pos-marker--mine" style={{ left: `${myPct}%` }}>
                        <span className="piq-pos-marker-dot" />
                        <span className="piq-pos-marker-tip">
                          <span className="piq-pos-marker-label">Dein Preis</span>
                          <span className="piq-pos-marker-price">{formatEuro(myPrice)}</span>
                        </span>
                      </div>
                    </div>
                    <div className="piq-comp-pos-range">
                      <span>{formatEuro(barMin)}</span>
                      <span>{formatEuro(barMax)}</span>
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
                            <td><span className="piq-comp-rank">#{idx + 1}</span> {c.name}</td>
                            <td style={{ textAlign: 'right' }}><span className="piq-price-current">{formatEuro(c.price)}</span></td>
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
      </s-page>
    </>
  );
}
