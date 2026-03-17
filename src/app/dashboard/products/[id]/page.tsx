'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useSearchParams } from 'next/navigation';
import { useState, useEffect, useRef } from 'react';
import {
  fetchProducts,
  getRecommendation,
  generateRecommendation,
  getCompetitorAnalysis,
  searchCompetitors,
  getProductCosts,
  saveProductCosts,
  applyPrice,
  explainPrice,
  chatWithAI,
} from '@/lib/api';
import { showToast } from '@/lib/toast';
import type { Recommendation } from '@/types/models';

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

  const [costInput, setCostInput] = useState('');
  const [shippingInput, setShippingInput] = useState('');
  const [packagingInput, setPackagingInput] = useState('');
  const [customsInput, setCustomsInput] = useState('');
  const [otherInput, setOtherInput] = useState('');
  const [payFeeInput, setPayFeeInput] = useState('2.9');
  const [vatInput, setVatInput] = useState('19');
  const [showDetails, setShowDetails] = useState(false);
  const [costSaved, setCostSaved] = useState(false);
  const [aiExplanation, setAiExplanation] = useState<{
    explanation: string; key_reason: string; confidence_text: string; action_hint: string;
  } | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  const costRef = useRef<HTMLElement>(null);
  const shippingRef = useRef<HTMLElement>(null);
  const packagingRef = useRef<HTMLElement>(null);
  const customsRef = useRef<HTMLElement>(null);
  const otherRef = useRef<HTMLElement>(null);
  const payFeeRef = useRef<HTMLElement>(null);
  const vatRef = useRef<HTMLElement>(null);
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
      setCostInput(String(existingCosts.purchase_cost || ''));
      if (existingCosts.shipping_cost) setShippingInput(String(existingCosts.shipping_cost));
      if (existingCosts.packaging_cost) setPackagingInput(String(existingCosts.packaging_cost));
      setCostSaved(true);
    }
  }, [existingCosts]);

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
      purchase_cost: parseFloat(costInput) || 0,
      shipping_cost: parseFloat(shippingInput) || 0,
      packaging_cost: parseFloat(packagingInput) || 0,
      payment_provider: 'stripe',
      payment_fee_percentage: parseFloat(payFeeInput) || 2.9,
      payment_fee_fixed: 0.30,
      country_code: 'DE', category: 'general',
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['costs', product?.shopify_product_id] }); setCostSaved(true); showToast('Kosten gespeichert!', { duration: 3000 }); },
    onError: () => showToast('Fehler beim Speichern', { isError: true }),
  });

  const competitorSearchMutation = useMutation({
    mutationFn: () => searchCompetitors(productId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['competitors', productId] }); showToast('Wettbewerber aktualisiert!', { duration: 3000 }); },
    onError: () => showToast('Competitor Search fehlgeschlagen', { isError: true }),
  });

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
    bind(costRef, (v) => { setCostInput(v); setCostSaved(false); });
    bind(shippingRef, (v) => { setShippingInput(v); setCostSaved(false); });
    bind(packagingRef, (v) => { setPackagingInput(v); setCostSaved(false); });
    bind(customsRef, (v) => { setCustomsInput(v); setCostSaved(false); });
    bind(otherRef, (v) => { setOtherInput(v); setCostSaved(false); });
    bind(payFeeRef, (v) => { setPayFeeInput(v); setCostSaved(false); });
    bind(vatRef, (v) => { setVatInput(v); setCostSaved(false); });
    bind(chatFieldRef, (v) => setChatInput(v));

    const chatEl = chatFieldRef.current;
    if (chatEl) {
      const keyHandler = (e: Event) => { if ((e as KeyboardEvent).key === 'Enter') document.getElementById('piq-chat-send')?.click(); };
      chatEl.addEventListener('keydown', keyHandler);
      cleanups.push(() => chatEl.removeEventListener('keydown', keyHandler));
    }
    return () => cleanups.forEach(fn => fn());
  }, []);

  const handleAiExplain = async () => {
    if (!recommendation) return;
    setAiLoading(true);
    setAiExplanation(null);
    try {
      const result = await explainPrice({
        current_price: recommendation.current_price, recommended_price: recommendation.recommended_price,
        confidence: recommendation.confidence ?? 0, price_change_pct: recommendation.price_change_pct ?? 0,
        strategies: recommendation.reasoning_object?.strategies as Record<string, unknown> | undefined,
        competitor_avg: recommendation.competitor_avg_price, break_even: hasEk ? ek : undefined,
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
        competitor_avg: recommendation?.competitor_avg_price, break_even: hasEk ? ek : undefined,
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

  const ek = parseFloat(costInput) || 0;
  const shipping = parseFloat(shippingInput) || 0;
  const packaging = parseFloat(packagingInput) || 0;
  const customs = parseFloat(customsInput) || 0;
  const other = parseFloat(otherInput) || 0;
  const payFeePct = parseFloat(payFeeInput) || 0;
  const vatRate = (parseFloat(vatInput) || 19) / 100;

  const totalFixedCosts = ek + shipping + packaging + customs + other;
  const hasEk = ek > 0;

  const calcPayFee = (price: number) => price * (payFeePct / 100) + 0.30;
  const totalCostCurrent = totalFixedCosts + (hasEk ? calcPayFee(currentPrice) : 0);
  const totalCostRec = totalFixedCosts + (hasEk && recommendedPrice > 0 ? calcPayFee(recommendedPrice) : 0);

  const netRevenueCurrent = currentPrice / (1 + vatRate);
  const netRevenueRec = recommendedPrice > 0 ? recommendedPrice / (1 + vatRate) : 0;

  const grossMarginCurrent = hasEk ? currentPrice - totalCostCurrent : 0;
  const grossMarginCurrentPct = hasEk && currentPrice > 0 ? (grossMarginCurrent / currentPrice) * 100 : 0;
  const grossMarginRec = hasEk && recommendedPrice > 0 ? recommendedPrice - totalCostRec : 0;
  const grossMarginRecPct = hasEk && recommendedPrice > 0 ? (grossMarginRec / recommendedPrice) * 100 : 0;

  const netProfitCurrent = hasEk ? netRevenueCurrent - totalCostCurrent : 0;
  const netProfitRec = hasEk && recommendedPrice > 0 ? netRevenueRec - totalCostRec : 0;
  const netProfitCurrentPct = hasEk && netRevenueCurrent > 0 ? (netProfitCurrent / netRevenueCurrent) * 100 : 0;
  const netProfitRecPct = hasEk && netRevenueRec > 0 ? (netProfitRec / netRevenueRec) * 100 : 0;

  const marginDiff = grossMarginRec - grossMarginCurrent;
  const roiCurrent = hasEk && totalCostCurrent > 0 ? (grossMarginCurrent / totalCostCurrent) * 100 : 0;
  const roiRec = hasEk && totalCostRec > 0 ? (grossMarginRec / totalCostRec) * 100 : 0;
  const breakEvenUnits = hasEk && grossMarginRec > 0 ? Math.ceil(totalCostRec / grossMarginRec) : 0;

  const hasDetailCosts = shipping > 0 || packaging > 0 || customs > 0 || other > 0 || payFeePct !== 2.9;
  const displayMarginPct = recommendation ? grossMarginRecPct : grossMarginCurrentPct;

  const barMin = Math.min(minPrice > 0 ? minPrice : Infinity, myPrice);
  const barMax = Math.max(maxPrice, myPrice);
  const barRange = barMax - barMin || 1;
  const cheapPct = minPrice > 0 ? Math.max(0, Math.min(100, ((minPrice - barMin) / barRange) * 100)) : 0;
  const avgPct = competition.avgPrice > 0 ? Math.max(0, Math.min(100, ((competition.avgPrice - barMin) / barRange) * 100)) : 50;
  const myPct = Math.max(0, Math.min(100, ((myPrice - barMin) / barRange) * 100));

  return (
    <>
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

          {/* ══ Margen-Rechner ══ */}
          <div className="piq-detail-card">
            <div className="piq-detail-card-head">
              <span className="piq-detail-section-lbl">Margen-Rechner</span>
              {hasEk && (
                <span className={`piq-detail-badge ${displayMarginPct >= 30 ? 'piq-detail-badge--green' : displayMarginPct >= 15 ? 'piq-detail-badge--amber' : 'piq-detail-badge--red'}`}>
                  Marge: {displayMarginPct.toFixed(1)}%
                </span>
              )}
            </div>
            <div className="piq-detail-card-body">

              {/* Basis-Eingabe: Einkaufspreis */}
              <div className="piq-margin-input-row">
                <div className="piq-margin-input-wrap">
                  <s-text-field ref={costRef} label="Einkaufspreis (netto, €)" type="number" value={costInput} placeholder="z.B. 120.00" help-text="Dein Netto-Einkaufspreis pro Stück ohne Versand und Gebühren" />
                </div>
              </div>

              {/* Aufklappbare Details */}
              <div className="piq-margin-toggle-row">
                <button className="piq-margin-toggle-btn" onClick={() => setShowDetails(!showDetails)} type="button">
                  <span className={`piq-margin-toggle-chevron ${showDetails ? 'piq-margin-toggle-chevron--open' : ''}`}>
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><path d="M4 2l4 4-4 4" /></svg>
                  </span>
                  {showDetails ? 'Weniger Details' : 'Detaillierte Kostenaufstellung'}
                  {hasDetailCosts && !showDetails && <span className="piq-margin-toggle-hint">({[shipping > 0 && 'Versand', packaging > 0 && 'Verpackung', customs > 0 && 'Zoll', other > 0 && 'Sonstiges'].filter(Boolean).join(', ')} hinterlegt)</span>}
                </button>
              </div>

              {showDetails && (
                <div className="piq-margin-details">
                  <div className="piq-margin-details-grid">
                    <div className="piq-margin-field">
                      <s-text-field ref={shippingRef} label="Versandkosten (€)" type="number" value={shippingInput} placeholder="0.00" help-text="Kosten für Versand pro Stück" />
                    </div>
                    <div className="piq-margin-field">
                      <s-text-field ref={packagingRef} label="Verpackung (€)" type="number" value={packagingInput} placeholder="0.00" help-text="Verpackungsmaterial pro Stück" />
                    </div>
                    <div className="piq-margin-field">
                      <s-text-field ref={customsRef} label="Zoll / Import (€)" type="number" value={customsInput} placeholder="0.00" help-text="Zollgebühren, Importsteuer pro Stück" />
                    </div>
                    <div className="piq-margin-field">
                      <s-text-field ref={otherRef} label="Sonstige Kosten (€)" type="number" value={otherInput} placeholder="0.00" help-text="Lager, Marketing, Retourenanteil etc." />
                    </div>
                    <div className="piq-margin-field">
                      <s-text-field ref={payFeeRef} label="Zahlungsgebühr (%)" type="number" value={payFeeInput} placeholder="2.9" help-text="z.B. Stripe 2,9%, PayPal 2,49%" />
                    </div>
                    <div className="piq-margin-field">
                      <s-text-field ref={vatRef} label="MwSt-Satz (%)" type="number" value={vatInput} placeholder="19" help-text="Standard DE: 19%, ermäßigt: 7%" />
                    </div>
                  </div>
                </div>
              )}

              {/* Speichern */}
              <div className="piq-margin-save-row">
                {hasEk && !costSaved && (
                  <button className="piq-cta piq-cta--primary piq-cta--sm" onClick={() => saveCostsMutation.mutate()} disabled={saveCostsMutation.isPending}>
                    {saveCostsMutation.isPending ? 'Speichert…' : 'Kosten speichern'}
                  </button>
                )}
                {costSaved && <span className="piq-margin-saved-hint">✓ Gespeichert</span>}
              </div>

              {/* Kostenübersicht (zusammengeklappt, aber Summe sichtbar) */}
              {hasEk && (
                <div className="piq-margin-cost-summary">
                  <div className="piq-margin-cost-summary-row">
                    <span className="piq-margin-cost-summary-lbl">Einkaufspreis</span>
                    <span className="piq-margin-cost-summary-val">{formatEuro(ek)}</span>
                  </div>
                  {shipping > 0 && (
                    <div className="piq-margin-cost-summary-row">
                      <span className="piq-margin-cost-summary-lbl">+ Versand</span>
                      <span className="piq-margin-cost-summary-val">{formatEuro(shipping)}</span>
                    </div>
                  )}
                  {packaging > 0 && (
                    <div className="piq-margin-cost-summary-row">
                      <span className="piq-margin-cost-summary-lbl">+ Verpackung</span>
                      <span className="piq-margin-cost-summary-val">{formatEuro(packaging)}</span>
                    </div>
                  )}
                  {customs > 0 && (
                    <div className="piq-margin-cost-summary-row">
                      <span className="piq-margin-cost-summary-lbl">+ Zoll / Import</span>
                      <span className="piq-margin-cost-summary-val">{formatEuro(customs)}</span>
                    </div>
                  )}
                  {other > 0 && (
                    <div className="piq-margin-cost-summary-row">
                      <span className="piq-margin-cost-summary-lbl">+ Sonstiges</span>
                      <span className="piq-margin-cost-summary-val">{formatEuro(other)}</span>
                    </div>
                  )}
                  {(recommendation ? calcPayFee(recommendedPrice) : calcPayFee(currentPrice)) > 0.30 && (
                    <div className="piq-margin-cost-summary-row">
                      <span className="piq-margin-cost-summary-lbl">+ Zahlungsgebühr ({payFeePct}%)</span>
                      <span className="piq-margin-cost-summary-val">{formatEuro(recommendation ? calcPayFee(recommendedPrice) : calcPayFee(currentPrice))}</span>
                    </div>
                  )}
                  <div className="piq-margin-cost-summary-row piq-margin-cost-summary-row--total">
                    <span className="piq-margin-cost-summary-lbl">Gesamtkosten pro Stück</span>
                    <span className="piq-margin-cost-summary-val">{formatEuro(recommendation ? totalCostRec : totalCostCurrent)}</span>
                  </div>
                </div>
              )}

              {/* Vergleich: Aktuell vs Empfohlen */}
              {hasEk && recommendation && (
                <div className="piq-margin-analysis">
                  <div className="piq-margin-compare">
                    <div className="piq-margin-compare-col">
                      <span className="piq-margin-compare-lbl">Aktueller Preis</span>
                      <span className="piq-margin-compare-price">{formatEuro(currentPrice)}</span>
                      <div className="piq-margin-compare-details">
                        <div className="piq-margin-kpi">
                          <span className="piq-margin-kpi-lbl">Brutto-Marge</span>
                          <span className={`piq-margin-kpi-val ${grossMarginCurrentPct >= 30 ? 'green' : grossMarginCurrentPct >= 15 ? 'amber' : 'red'}`}>
                            {formatEuro(grossMarginCurrent)} ({grossMarginCurrentPct.toFixed(1)}%)
                          </span>
                        </div>
                        <div className="piq-margin-kpi">
                          <span className="piq-margin-kpi-lbl">Netto-Gewinn</span>
                          <span className={`piq-margin-kpi-val ${netProfitCurrent >= 0 ? 'green' : 'red'}`}>
                            {formatEuro(netProfitCurrent)} ({netProfitCurrentPct.toFixed(1)}%)
                          </span>
                        </div>
                        <div className="piq-margin-kpi">
                          <span className="piq-margin-kpi-lbl">ROI</span>
                          <span className="piq-margin-kpi-val">{roiCurrent.toFixed(0)}%</span>
                        </div>
                      </div>
                    </div>
                    <div className="piq-margin-compare-arrow">→</div>
                    <div className="piq-margin-compare-col piq-margin-compare-col--rec">
                      <span className="piq-margin-compare-lbl">Empfohlener Preis</span>
                      <span className="piq-margin-compare-price">{formatEuro(recommendedPrice)}</span>
                      <div className="piq-margin-compare-details">
                        <div className="piq-margin-kpi">
                          <span className="piq-margin-kpi-lbl">Brutto-Marge</span>
                          <span className={`piq-margin-kpi-val ${grossMarginRecPct >= 30 ? 'green' : grossMarginRecPct >= 15 ? 'amber' : 'red'}`}>
                            {formatEuro(grossMarginRec)} ({grossMarginRecPct.toFixed(1)}%)
                          </span>
                        </div>
                        <div className="piq-margin-kpi">
                          <span className="piq-margin-kpi-lbl">Netto-Gewinn</span>
                          <span className={`piq-margin-kpi-val ${netProfitRec >= 0 ? 'green' : 'red'}`}>
                            {formatEuro(netProfitRec)} ({netProfitRecPct.toFixed(1)}%)
                          </span>
                        </div>
                        <div className="piq-margin-kpi">
                          <span className="piq-margin-kpi-lbl">ROI</span>
                          <span className="piq-margin-kpi-val">{roiRec.toFixed(0)}%</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="piq-margin-insights">
                    <div className="piq-margin-insight-item">
                      <span className="piq-margin-insight-icon">{marginDiff >= 0 ? '📈' : '📉'}</span>
                      <span className="piq-margin-insight-text">
                        {marginDiff >= 0
                          ? `+${formatEuro(marginDiff)} mehr Gewinn pro Stück mit dem empfohlenen Preis`
                          : `${formatEuro(Math.abs(marginDiff))} weniger Gewinn, aber höheres Verkaufsvolumen erwartet`}
                      </span>
                    </div>
                    <div className="piq-margin-insight-item">
                      <span className="piq-margin-insight-icon">🏷️</span>
                      <span className="piq-margin-insight-text">
                        Netto nach {(vatRate * 100).toFixed(0)}% MwSt: {formatEuro(netProfitRec)} Gewinn pro Stück
                      </span>
                    </div>
                    {breakEvenUnits > 0 && (
                      <div className="piq-margin-insight-item">
                        <span className="piq-margin-insight-icon">⚖️</span>
                        <span className="piq-margin-insight-text">
                          Ab {breakEvenUnits} verkauften Stück hast du alle Kosten refinanziert
                        </span>
                      </div>
                    )}
                    {(shipping > 0 || packaging > 0 || customs > 0 || other > 0) && (
                      <div className="piq-margin-insight-item">
                        <span className="piq-margin-insight-icon">📦</span>
                        <span className="piq-margin-insight-text">
                          Nebenkosten machen {formatEuro(shipping + packaging + customs + other)} ({((shipping + packaging + customs + other) / totalCostRec * 100).toFixed(1)}%) deiner Gesamtkosten aus
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Nur aktueller Preis (kein Empfehlung) */}
              {hasEk && !recommendation && (
                <div className="piq-margin-analysis">
                  <div className="piq-margin-insights">
                    <div className="piq-margin-insight-item">
                      <span className="piq-margin-insight-icon">📊</span>
                      <span className="piq-margin-insight-text">
                        Brutto-Marge: {formatEuro(grossMarginCurrent)} ({grossMarginCurrentPct.toFixed(1)}%) pro Stück
                      </span>
                    </div>
                    <div className="piq-margin-insight-item">
                      <span className="piq-margin-insight-icon">💰</span>
                      <span className="piq-margin-insight-text">
                        Netto-Gewinn nach MwSt: {formatEuro(netProfitCurrent)} ({netProfitCurrentPct.toFixed(1)}%)
                      </span>
                    </div>
                    <div className="piq-margin-insight-item">
                      <span className="piq-margin-insight-icon">💡</span>
                      <span className="piq-margin-insight-text">
                        Generiere eine Empfehlung um den Margen-Vergleich zu sehen
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {!hasEk && (
                <div className="piq-margin-empty">
                  <span className="piq-margin-empty-text">Gib deinen Einkaufspreis ein um Marge, ROI und Gewinn pro Stück zu berechnen.</span>
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
                    <div className="piq-comp-bar-container">
                      <div className="piq-comp-bar-labels-top">
                        {minPrice > 0 && (
                          <div className="piq-bar-label piq-bar-label--cheap" style={{ left: `${cheapPct}%` }}>
                            <span className="piq-bar-label-price">{formatEuro(minPrice)}</span>
                            <span className="piq-bar-label-name">Günstigster</span>
                          </div>
                        )}
                        <div className="piq-bar-label piq-bar-label--mine" style={{ left: `${myPct}%` }}>
                          <span className="piq-bar-label-price">{formatEuro(myPrice)}</span>
                          <span className="piq-bar-label-name">Dein Preis</span>
                        </div>
                      </div>
                      <div className="piq-comp-pos-track">
                        {minPrice > 0 && <div className="piq-bar-dot piq-bar-dot--cheap" style={{ left: `${cheapPct}%` }} />}
                        {competition.avgPrice > 0 && <div className="piq-bar-dot piq-bar-dot--avg" style={{ left: `${avgPct}%` }} />}
                        <div className="piq-bar-dot piq-bar-dot--mine" style={{ left: `${myPct}%` }} />
                      </div>
                      <div className="piq-comp-bar-labels-bottom">
                        {competition.avgPrice > 0 && (
                          <div className="piq-bar-label piq-bar-label--avg" style={{ left: `${avgPct}%` }}>
                            <span className="piq-bar-label-name">Ø Markt</span>
                            <span className="piq-bar-label-price">{formatEuro(competition.avgPrice)}</span>
                          </div>
                        )}
                      </div>
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
