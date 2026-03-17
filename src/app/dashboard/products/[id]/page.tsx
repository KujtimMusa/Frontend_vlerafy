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
  const [inboundShipInput, setInboundShipInput] = useState('');
  const [customsInput, setCustomsInput] = useState('');
  const [packagingInput, setPackagingInput] = useState('');
  const [outboundShipInput, setOutboundShipInput] = useState('');
  const [fulfillmentInput, setFulfillmentInput] = useState('');
  const [payFeePctInput, setPayFeePctInput] = useState('2.9');
  const [payFeeFixInput, setPayFeeFixInput] = useState('0.30');
  const [platformFeePctInput, setPlatformFeePctInput] = useState('0');
  const [storageInput, setStorageInput] = useState('');
  const [marketingInput, setMarketingInput] = useState('');
  const [returnRateInput, setReturnRateInput] = useState('');
  const [otherInput, setOtherInput] = useState('');
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
  const inboundShipRef = useRef<HTMLElement>(null);
  const customsRef2 = useRef<HTMLElement>(null);
  const packagingRef = useRef<HTMLElement>(null);
  const outboundShipRef = useRef<HTMLElement>(null);
  const fulfillmentRef = useRef<HTMLElement>(null);
  const payFeePctRef = useRef<HTMLElement>(null);
  const payFeeFixRef = useRef<HTMLElement>(null);
  const platformFeePctRef = useRef<HTMLElement>(null);
  const storageRef = useRef<HTMLElement>(null);
  const marketingRef = useRef<HTMLElement>(null);
  const returnRateRef = useRef<HTMLElement>(null);
  const otherRef = useRef<HTMLElement>(null);
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
      if (existingCosts.shipping_cost) setInboundShipInput(String(existingCosts.shipping_cost));
      if (existingCosts.packaging_cost) setPackagingInput(String(existingCosts.packaging_cost));
      if (existingCosts.payment_fee_percentage) setPayFeePctInput(String(existingCosts.payment_fee_percentage));
      if (existingCosts.payment_fee_fixed) setPayFeeFixInput(String(existingCosts.payment_fee_fixed));
      if (existingCosts.vat_rate) setVatInput(String(existingCosts.vat_rate));
      setCostSaved(true);
    }
  }, [existingCosts]);

  useEffect(() => {
    if (!product?.shopify_product_id) return;
    try {
      const raw = localStorage.getItem(`vlerafy-extra-costs-${product.shopify_product_id}`);
      if (!raw) return;
      const d = JSON.parse(raw);
      if (d.customs) setCustomsInput(d.customs);
      if (d.outboundShip) setOutboundShipInput(d.outboundShip);
      if (d.fulfillment) setFulfillmentInput(d.fulfillment);
      if (d.platformFeePct) setPlatformFeePctInput(d.platformFeePct);
      if (d.storage) setStorageInput(d.storage);
      if (d.marketing) setMarketingInput(d.marketing);
      if (d.returnRate) setReturnRateInput(d.returnRate);
      if (d.other) setOtherInput(d.other);
    } catch { /* ignore */ }
  }, [product?.shopify_product_id]);

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
    mutationFn: async () => {
      const pid = product!.shopify_product_id;
      await saveProductCosts({
        product_id: pid,
        purchase_cost: parseFloat(costInput) || 0,
        shipping_cost: parseFloat(inboundShipInput) || 0,
        packaging_cost: parseFloat(packagingInput) || 0,
        payment_provider: 'stripe',
        payment_fee_percentage: parseFloat(payFeePctInput) || 2.9,
        payment_fee_fixed: parseFloat(payFeeFixInput) || 0.30,
        country_code: 'DE', category: 'general',
      });
      localStorage.setItem(`vlerafy-extra-costs-${pid}`, JSON.stringify({
        customs: customsInput, outboundShip: outboundShipInput,
        fulfillment: fulfillmentInput, platformFeePct: platformFeePctInput,
        storage: storageInput, marketing: marketingInput,
        returnRate: returnRateInput, other: otherInput,
      }));
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['costs', product?.shopify_product_id] }); setCostSaved(true); showToast('Alle Kosten gespeichert!', { duration: 3000 }); },
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
    const dirty = (setter: (v: string) => void) => (v: string) => { setter(v); setCostSaved(false); };
    bind(costRef, dirty(setCostInput));
    bind(inboundShipRef, dirty(setInboundShipInput));
    bind(customsRef2, dirty(setCustomsInput));
    bind(packagingRef, dirty(setPackagingInput));
    bind(outboundShipRef, dirty(setOutboundShipInput));
    bind(fulfillmentRef, dirty(setFulfillmentInput));
    bind(payFeePctRef, dirty(setPayFeePctInput));
    bind(payFeeFixRef, dirty(setPayFeeFixInput));
    bind(platformFeePctRef, dirty(setPlatformFeePctInput));
    bind(storageRef, dirty(setStorageInput));
    bind(marketingRef, dirty(setMarketingInput));
    bind(returnRateRef, dirty(setReturnRateInput));
    bind(otherRef, dirty(setOtherInput));
    bind(vatRef, dirty(setVatInput));
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
  const inboundShip = parseFloat(inboundShipInput) || 0;
  const customs = parseFloat(customsInput) || 0;
  const packaging = parseFloat(packagingInput) || 0;
  const outboundShip = parseFloat(outboundShipInput) || 0;
  const fulfillment = parseFloat(fulfillmentInput) || 0;
  const payFeePct = parseFloat(payFeePctInput) || 0;
  const payFeeFix = parseFloat(payFeeFixInput) || 0;
  const platformFeePct = parseFloat(platformFeePctInput) || 0;
  const storageCost = parseFloat(storageInput) || 0;
  const marketingCost = parseFloat(marketingInput) || 0;
  const returnRate = parseFloat(returnRateInput) || 0;
  const other = parseFloat(otherInput) || 0;
  const vatRate = (parseFloat(vatInput) || 19) / 100;
  const hasEk = ek > 0;

  const cogsFixed = ek + inboundShip + customs + packaging;
  const fulfillFixed = outboundShip + fulfillment;
  const opsFixed = storageCost + marketingCost + other;
  const totalFixedCosts = cogsFixed + fulfillFixed + opsFixed;

  const calcPayFee = (price: number) => price * (payFeePct / 100) + payFeeFix;
  const calcPlatformFee = (price: number) => price * (platformFeePct / 100);
  const totalVarCosts = (price: number) => calcPayFee(price) + calcPlatformFee(price);

  const totalCostCurrent = totalFixedCosts + (hasEk ? totalVarCosts(currentPrice) : 0);
  const totalCostRec = totalFixedCosts + (hasEk && recommendedPrice > 0 ? totalVarCosts(recommendedPrice) : 0);

  const returnMultiplier = returnRate > 0 ? 1 / (1 - returnRate / 100) : 1;
  const effectiveCostCurrent = totalCostCurrent * returnMultiplier;
  const effectiveCostRec = totalCostRec * returnMultiplier;

  const netRevenueCurrent = currentPrice / (1 + vatRate);
  const netRevenueRec = recommendedPrice > 0 ? recommendedPrice / (1 + vatRate) : 0;

  const grossMarginCurrent = hasEk ? currentPrice - effectiveCostCurrent : 0;
  const grossMarginCurrentPct = hasEk && currentPrice > 0 ? (grossMarginCurrent / currentPrice) * 100 : 0;
  const grossMarginRec = hasEk && recommendedPrice > 0 ? recommendedPrice - effectiveCostRec : 0;
  const grossMarginRecPct = hasEk && recommendedPrice > 0 ? (grossMarginRec / recommendedPrice) * 100 : 0;

  const netProfitCurrent = hasEk ? netRevenueCurrent - effectiveCostCurrent : 0;
  const netProfitRec = hasEk && recommendedPrice > 0 ? netRevenueRec - effectiveCostRec : 0;
  const netProfitCurrentPct = hasEk && netRevenueCurrent > 0 ? (netProfitCurrent / netRevenueCurrent) * 100 : 0;
  const netProfitRecPct = hasEk && netRevenueRec > 0 ? (netProfitRec / netRevenueRec) * 100 : 0;

  const marginDiff = grossMarginRec - grossMarginCurrent;
  const roiCurrent = hasEk && effectiveCostCurrent > 0 ? (grossMarginCurrent / effectiveCostCurrent) * 100 : 0;
  const roiRec = hasEk && effectiveCostRec > 0 ? (grossMarginRec / effectiveCostRec) * 100 : 0;
  const breakEvenUnits = hasEk && grossMarginRec > 0 ? Math.ceil(effectiveCostRec / grossMarginRec) : 0;

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

              <div className="piq-margin-input-row">
                <div className="piq-margin-input-wrap piq-margin-input-wrap--wide">
                  <s-text-field ref={costRef} label="Einkaufspreis (netto, €)" type="number" value={costInput} placeholder="z.B. 120.00" help-text="Netto-Einkaufspreis pro Stück ohne Nebenkosten" />
                </div>
              </div>

              <div className="piq-margin-toggle-row">
                <button className="piq-margin-toggle-btn" onClick={() => setShowDetails(!showDetails)} type="button">
                  <span className={`piq-margin-toggle-chevron ${showDetails ? 'piq-margin-toggle-chevron--open' : ''}`}>
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><path d="M4 2l4 4-4 4" /></svg>
                  </span>
                  {showDetails ? 'Weniger Details' : 'Alle Kosten aufschlüsseln'}
                </button>
              </div>

              {/* Detail-Felder: IMMER im DOM (CSS toggle), damit Refs korrekt binden */}
              <div className="piq-margin-details" style={{ display: showDetails ? 'block' : 'none' }}>

                <div className="piq-margin-group">
                  <span className="piq-margin-group-lbl">Warenbezug</span>
                  <div className="piq-margin-details-grid">
                    <div className="piq-margin-field">
                      <s-text-field ref={inboundShipRef} label="Fracht zum Lager (€)" type="number" value={inboundShipInput} placeholder="0.00" help-text="Transport vom Lieferanten zu deinem Lager, pro Stück" />
                    </div>
                    <div className="piq-margin-field">
                      <s-text-field ref={customsRef2} label="Zoll & Einfuhrumsatzsteuer (€)" type="number" value={customsInput} placeholder="0.00" help-text="Zollgebühren + Einfuhrumsatzsteuer pro Stück" />
                    </div>
                    <div className="piq-margin-field">
                      <s-text-field ref={packagingRef} label="Verpackungsmaterial (€)" type="number" value={packagingInput} placeholder="0.00" help-text="Karton, Füllmaterial, Klebeband pro Stück" />
                    </div>
                  </div>
                </div>

                <div className="piq-margin-group">
                  <span className="piq-margin-group-lbl">Versand & Fulfillment</span>
                  <div className="piq-margin-details-grid">
                    <div className="piq-margin-field">
                      <s-text-field ref={outboundShipRef} label="Versand an Kunden (€)" type="number" value={outboundShipInput} placeholder="0.00" help-text="Versandkosten pro Paket an den Endkunden" />
                    </div>
                    <div className="piq-margin-field">
                      <s-text-field ref={fulfillmentRef} label="Fulfillment / Handling (€)" type="number" value={fulfillmentInput} placeholder="0.00" help-text="Picking, Packing, Labeling pro Bestellung" />
                    </div>
                  </div>
                </div>

                <div className="piq-margin-group">
                  <span className="piq-margin-group-lbl">Gebühren & Transaktionen</span>
                  <div className="piq-margin-details-grid">
                    <div className="piq-margin-field">
                      <s-text-field ref={payFeePctRef} label="Zahlungsgebühr (%)" type="number" value={payFeePctInput} placeholder="2.9" help-text="Stripe: 2,9%, PayPal: 2,49%, Klarna: 2,99%" />
                    </div>
                    <div className="piq-margin-field">
                      <s-text-field ref={payFeeFixRef} label="Zahlungsgebühr fix (€)" type="number" value={payFeeFixInput} placeholder="0.30" help-text="Fixbetrag pro Transaktion (z.B. 0,30 €)" />
                    </div>
                    <div className="piq-margin-field">
                      <s-text-field ref={platformFeePctRef} label="Shopify/Plattform-Gebühr (%)" type="number" value={platformFeePctInput} placeholder="0" help-text="Shopify Payments: 0%, Basic Plan Transaction Fee: 2%" />
                    </div>
                  </div>
                </div>

                <div className="piq-margin-group">
                  <span className="piq-margin-group-lbl">Betrieb & Marketing</span>
                  <div className="piq-margin-details-grid">
                    <div className="piq-margin-field">
                      <s-text-field ref={storageRef} label="Lagerkosten (€/Stück)" type="number" value={storageInput} placeholder="0.00" help-text="Anteilige Lagermiete, Strom etc. pro Stück" />
                    </div>
                    <div className="piq-margin-field">
                      <s-text-field ref={marketingRef} label="Marketing (€/Stück)" type="number" value={marketingInput} placeholder="0.00" help-text="Werbekosten pro verkauftem Stück (CAC)" />
                    </div>
                    <div className="piq-margin-field">
                      <s-text-field ref={returnRateRef} label="Retourenquote (%)" type="number" value={returnRateInput} placeholder="0" help-text="Erwartete Rücksendequote – erhöht effektive Kosten pro Sale" />
                    </div>
                    <div className="piq-margin-field">
                      <s-text-field ref={otherRef} label="Sonstige Kosten (€)" type="number" value={otherInput} placeholder="0.00" help-text="Kundenservice, Garantie, sonstige Fixkosten pro Stück" />
                    </div>
                  </div>
                </div>

                <div className="piq-margin-group">
                  <span className="piq-margin-group-lbl">Steuern</span>
                  <div className="piq-margin-details-grid">
                    <div className="piq-margin-field">
                      <s-text-field ref={vatRef} label="MwSt-Satz (%)" type="number" value={vatInput} placeholder="19" help-text="Deutschland: 19% (Standard) oder 7% (ermäßigt)" />
                    </div>
                  </div>
                </div>

              </div>

              {/* Speichern */}
              <div className="piq-margin-save-row">
                {hasEk && !costSaved && (
                  <button className="piq-cta piq-cta--primary piq-cta--sm" onClick={() => saveCostsMutation.mutate()} disabled={saveCostsMutation.isPending}>
                    {saveCostsMutation.isPending ? 'Speichert…' : 'Alle Kosten speichern'}
                  </button>
                )}
                {costSaved && <span className="piq-margin-saved-hint">✓ Gespeichert</span>}
              </div>

              {/* Kostenübersicht */}
              {hasEk && (
                <div className="piq-margin-cost-summary">
                  <div className="piq-margin-cost-summary-row"><span className="piq-margin-cost-summary-lbl">Einkaufspreis</span><span className="piq-margin-cost-summary-val">{formatEuro(ek)}</span></div>
                  {inboundShip > 0 && <div className="piq-margin-cost-summary-row"><span className="piq-margin-cost-summary-lbl">+ Fracht zum Lager</span><span className="piq-margin-cost-summary-val">{formatEuro(inboundShip)}</span></div>}
                  {customs > 0 && <div className="piq-margin-cost-summary-row"><span className="piq-margin-cost-summary-lbl">+ Zoll & Einfuhr</span><span className="piq-margin-cost-summary-val">{formatEuro(customs)}</span></div>}
                  {packaging > 0 && <div className="piq-margin-cost-summary-row"><span className="piq-margin-cost-summary-lbl">+ Verpackung</span><span className="piq-margin-cost-summary-val">{formatEuro(packaging)}</span></div>}
                  {outboundShip > 0 && <div className="piq-margin-cost-summary-row"><span className="piq-margin-cost-summary-lbl">+ Versand an Kunden</span><span className="piq-margin-cost-summary-val">{formatEuro(outboundShip)}</span></div>}
                  {fulfillment > 0 && <div className="piq-margin-cost-summary-row"><span className="piq-margin-cost-summary-lbl">+ Fulfillment</span><span className="piq-margin-cost-summary-val">{formatEuro(fulfillment)}</span></div>}
                  {storageCost > 0 && <div className="piq-margin-cost-summary-row"><span className="piq-margin-cost-summary-lbl">+ Lagerkosten</span><span className="piq-margin-cost-summary-val">{formatEuro(storageCost)}</span></div>}
                  {marketingCost > 0 && <div className="piq-margin-cost-summary-row"><span className="piq-margin-cost-summary-lbl">+ Marketing</span><span className="piq-margin-cost-summary-val">{formatEuro(marketingCost)}</span></div>}
                  {other > 0 && <div className="piq-margin-cost-summary-row"><span className="piq-margin-cost-summary-lbl">+ Sonstiges</span><span className="piq-margin-cost-summary-val">{formatEuro(other)}</span></div>}
                  {totalVarCosts(recommendation ? recommendedPrice : currentPrice) > 0 && (
                    <div className="piq-margin-cost-summary-row">
                      <span className="piq-margin-cost-summary-lbl">+ Gebühren ({payFeePct}% + {formatEuro(payFeeFix)}{platformFeePct > 0 ? ` + ${platformFeePct}% Plattform` : ''})</span>
                      <span className="piq-margin-cost-summary-val">{formatEuro(totalVarCosts(recommendation ? recommendedPrice : currentPrice))}</span>
                    </div>
                  )}
                  {returnRate > 0 && (
                    <div className="piq-margin-cost-summary-row piq-margin-cost-summary-row--warn">
                      <span className="piq-margin-cost-summary-lbl">⚠ Retouren-Aufschlag ({returnRate}%)</span>
                      <span className="piq-margin-cost-summary-val">+{formatEuro((recommendation ? effectiveCostRec : effectiveCostCurrent) - (recommendation ? totalCostRec : totalCostCurrent))}</span>
                    </div>
                  )}
                  <div className="piq-margin-cost-summary-row piq-margin-cost-summary-row--total">
                    <span className="piq-margin-cost-summary-lbl">Gesamtkosten pro Stück</span>
                    <span className="piq-margin-cost-summary-val">{formatEuro(recommendation ? effectiveCostRec : effectiveCostCurrent)}</span>
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
                    {returnRate > 0 && (
                      <div className="piq-margin-insight-item">
                        <span className="piq-margin-insight-icon">🔄</span>
                        <span className="piq-margin-insight-text">
                          {returnRate}% Retourenquote erhöht deine effektiven Kosten um {formatEuro((effectiveCostRec - totalCostRec))} pro erfolgreichem Verkauf
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}

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
