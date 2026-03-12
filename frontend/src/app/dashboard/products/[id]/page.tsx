'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'next/navigation';
import { useState, useEffect } from 'react';
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
  markRecommendationApplied,
  getCategoryDefaults,
} from '@/lib/api';
import { showToast } from '@/lib/toast';
import type { Recommendation } from '@/types/models';

const PAYMENT_PROVIDERS = [
  { label: 'Stripe (2.9% + 0.30€)', value: 'stripe' },
  { label: 'PayPal (2.49% + 0.35€)', value: 'paypal' },
  { label: 'Klarna (4.5%)', value: 'klarna' },
  { label: 'Custom', value: 'custom' },
];

const CATEGORIES = ['fashion', 'electronics', 'beauty', 'home', 'food'];

export default function ProductDetailPage() {
  const { id } = useParams();
  const productId = Number(id);
  const qc = useQueryClient();

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
    queryFn: () =>
      getProductCosts(product?.shopify_product_id ?? ''),
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
    onError: () =>
      showToast('Fehler beim Generieren', { isError: true }),
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
    onError: () =>
      showToast('Fehler beim Übernehmen', { isError: true }),
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
    onError: () =>
      showToast('Fehler beim Speichern', { isError: true }),
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

  if (!product) return <s-skeleton-page />;

  const raw =
    typeof recommendation?.reasoning === 'object'
      ? (recommendation.reasoning as Record<string, unknown>)?.summary ??
        JSON.stringify(recommendation.reasoning)
      : recommendation?.reasoning ?? '';
  const reasoningText =
    typeof raw === 'string' ? raw : JSON.stringify(raw);

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
  const compDisplay = compList.map((c: { title?: string; competitor_name?: string; price: number; url?: string; source?: string; competitor_url?: string }) => ({
    title: c.title ?? c.competitor_name ?? 'Unbekannt',
    price: c.price,
    source: c.source ?? c.competitor_name ?? '–',
    url: c.url ?? c.competitor_url ?? '',
  }));

  return (
    <s-page
      title={product.title}
      back-action='{"content":"Produkte","url":"/dashboard/products"}'
    >
      <s-layout>
        {/* ── CARD 1: ML Preisempfehlung ── */}
        <s-card title="KI-Preisempfehlung">
          {recLoading ? (
            <s-skeleton-body-text />
          ) : recommendation ? (
            <>
              <s-layout variant="1-1">
                <div>
                  <s-text tone="subdued">Aktueller Preis</s-text>
                  <s-text variant="headingXl">€{product.price}</s-text>
                </div>
                <div>
                  <s-badge tone="info">{recommendation.strategy}</s-badge>
                  <s-text tone="subdued">Empfohlener Preis</s-text>
                  <s-text variant="headingXl">
                    €{recommendation.recommended_price}
                  </s-text>
                  <s-text
                    tone={
                      recommendation.price_change_pct >= 0
                        ? 'success'
                        : 'critical'
                    }
                  >
                    {recommendation.price_change_pct >= 0 ? '+' : ''}
                    {recommendation.price_change_pct.toFixed(1)}%
                  </s-text>
                </div>
              </s-layout>

              <s-text variant="headingMd">Konfidenz</s-text>
              <s-layout variant="1-1-1">
                <div>
                  <s-text tone="subdued">Gesamt</s-text>
                  <s-badge
                    tone={
                      confidencePct >= 80
                        ? 'success'
                        : confidencePct >= 60
                          ? 'warning'
                          : 'critical'
                    }
                  >
                    {confidencePct}% {recommendation.confidence_label ?? ''}
                  </s-badge>
                </div>
                {mlConfidencePct != null && (
                  <div>
                    <s-text tone="subdued">XGBoost</s-text>
                    <s-badge
                      tone={mlConfidencePct >= 80 ? 'success' : 'warning'}
                    >
                      {mlConfidencePct}%
                    </s-badge>
                  </div>
                )}
                {metaConfidencePct != null && (
                  <div>
                    <s-text tone="subdued">Meta-Labeler</s-text>
                    <s-badge
                      tone={
                        recommendation.meta_labeler_approved
                          ? 'success'
                          : 'warning'
                      }
                    >
                      {metaConfidencePct}%{' '}
                      {recommendation.meta_labeler_approved ? '✓' : '✗'}
                    </s-badge>
                  </div>
                )}
              </s-layout>

              {recommendation.competitor_avg_price != null && (
                <s-layout variant="1-1-1">
                  <div>
                    <s-text tone="subdued">Nachfragewachstum</s-text>
                    <s-text>
                      {recommendation.demand_growth != null
                        ? `${(recommendation.demand_growth * 100).toFixed(1)}%`
                        : '–'}
                    </s-text>
                  </div>
                  <div>
                    <s-text tone="subdued">Tage Lagerbestand</s-text>
                    <s-text>
                      {recommendation.days_of_stock?.toFixed(0) ?? '–'}
                    </s-text>
                  </div>
                  <div>
                    <s-text tone="subdued">Wettbewerber Ø</s-text>
                    <s-text>
                      €{recommendation.competitor_avg_price.toFixed(2)}
                    </s-text>
                  </div>
                </s-layout>
              )}

              {recommendation.strategy_details &&
                recommendation.strategy_details.length > 0 && (
                  <s-collapsible title="Strategie Details">
                    {recommendation.strategy_details.map((detail, i) => (
                      <s-card key={i}>
                        <s-badge>{detail.strategy}</s-badge>
                        <s-text>
                          €{detail.recommended_price} – {detail.reasoning}
                        </s-text>
                      </s-card>
                    ))}
                  </s-collapsible>
                )}

              <s-text variant="headingMd">Begründung</s-text>
              <s-text>{reasoningText}</s-text>

              <s-layout variant="1-1">
                <s-button
                  variant="primary"
                  onClick={() => applyMutation.mutate()}
                  loading={applyMutation.isPending}
                >
                  Preis übernehmen (€{recommendation.recommended_price})
                </s-button>
                <s-button
                  onClick={() => generateMutation.mutate()}
                  loading={generateMutation.isPending}
                >
                  Neu generieren
                </s-button>
              </s-layout>
            </>
          ) : (
            <>
              <s-text tone="subdued">
                Noch keine Empfehlung für dieses Produkt.
              </s-text>
              <s-button
                variant="primary"
                onClick={() => generateMutation.mutate()}
                loading={generateMutation.isPending}
              >
                Empfehlung generieren
              </s-button>
            </>
          )}
        </s-card>

        {/* ── CARD 2: Margen-Analyse ── */}
        <s-card title="Margen-Analyse">
          {margin?.has_cost_data ? (
            <>
              <s-layout variant="1-1">
                <div>
                  <s-text tone="subdued">Verkaufspreis</s-text>
                  <s-text variant="headingLg">
                    €{margin.selling_price}
                  </s-text>
                </div>
                <div>
                  <s-text tone="subdued">Nettoerlös</s-text>
                  <s-text variant="headingLg">
                    €{margin.net_revenue.toFixed(2)}
                  </s-text>
                </div>
              </s-layout>

              <s-text variant="headingMd">Kostenaufstellung</s-text>
              <s-list-item>
                Einkauf: €{margin.costs.purchase.toFixed(2)}
              </s-list-item>
              <s-list-item>
                Versand: €{margin.costs.shipping.toFixed(2)}
              </s-list-item>
              <s-list-item>
                Verpackung: €{margin.costs.packaging.toFixed(2)}
              </s-list-item>
              <s-list-item>
                Zahlungsgebühr ({margin.payment_provider}): €
                {margin.costs.payment_fee.toFixed(2)}
              </s-list-item>
              <s-list-item>
                <strong>
                  Gesamt: €{margin.costs.total_variable.toFixed(2)}
                </strong>
              </s-list-item>

              <s-text variant="headingMd">
                Deckungsbeitrag: €{margin.margin.euro.toFixed(2)} (
                {margin.margin.percent.toFixed(1)}%)
              </s-text>
              <s-progress-bar value={margin.margin.percent} max={100} />

              <s-text variant="headingMd">Preis-Benchmarks</s-text>
              <s-list-item>
                Break-Even: €{margin.break_even_price.toFixed(2)}
                <s-badge
                  tone={
                    margin.is_above_break_even ? 'success' : 'critical'
                  }
                >
                  {margin.is_above_break_even ? '✓ OK' : '✗ Unter Break-Even'}
                </s-badge>
              </s-list-item>
              <s-list-item>
                Mindestpreis (20% Marge): €
                {margin.recommended_min_price.toFixed(2)}
                <s-badge
                  tone={margin.is_above_min_margin ? 'success' : 'warning'}
                >
                  {margin.is_above_min_margin ? '✓ OK' : '⚠ Unter Mindestmarge'}
                </s-badge>
              </s-list-item>
              <s-list-item>
                MwSt: {margin.vat_rate}% ({margin.country_code})
              </s-list-item>

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
            <s-card title="Kostendaten eingeben">
              <label>
                Kategorie (lädt Standardwerte)
                <select
                  value={costForm.category}
                  onChange={(e) =>
                    loadCategoryDefaults(e.target.value)
                  }
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Einkaufspreis (€)
                <input
                  type="number"
                  value={costForm.purchase_cost}
                  onChange={(e) =>
                    setCostForm((p) => ({ ...p, purchase_cost: e.target.value }))
                  }
                />
              </label>
              <label>
                Versandkosten (€)
                <input
                  type="number"
                  value={costForm.shipping_cost}
                  onChange={(e) =>
                    setCostForm((p) => ({ ...p, shipping_cost: e.target.value }))
                  }
                />
              </label>
              <label>
                Verpackungskosten (€)
                <input
                  type="number"
                  value={costForm.packaging_cost}
                  onChange={(e) =>
                    setCostForm((p) => ({
                      ...p,
                      packaging_cost: e.target.value,
                    }))
                  }
                />
              </label>
              <label>
                Zahlungsanbieter
                <select
                  value={costForm.payment_provider}
                  onChange={(e) =>
                    setCostForm((p) => ({
                      ...p,
                      payment_provider: e.target.value,
                    }))
                  }
                >
                  {PAYMENT_PROVIDERS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </label>
              <s-layout variant="1-1">
                <s-button
                  variant="primary"
                  onClick={() => saveCostsMutation.mutate()}
                  loading={saveCostsMutation.isPending}
                >
                  Speichern & Marge berechnen
                </s-button>
                {showCostForm && (
                  <s-button onClick={() => setShowCostForm(false)}>
                    Abbrechen
                  </s-button>
                )}
              </s-layout>
            </s-card>
          )}
        </s-card>

        {/* ── CARD 3: Wettbewerbsanalyse ── */}
        <s-card title="Wettbewerbsanalyse">
          {compLoading ? (
            <s-skeleton-body-text />
          ) : competitors?.has_data ? (
            <>
              <s-layout variant="1-1-1">
                <div>
                  <s-text tone="subdued">Dein Preis</s-text>
                  <s-text variant="headingLg">
                    €{competitors.current_price}
                  </s-text>
                </div>
                <div>
                  <s-text tone="subdued">Marktdurchschnitt</s-text>
                  <s-text variant="headingLg">
                    €{competitors.competitor_avg?.toFixed(2)}
                  </s-text>
                  <s-text tone="subdued">
                    {competitors.competitor_count} Anbieter
                  </s-text>
                </div>
                <div>
                  <s-text tone="subdued">Preisspanne</s-text>
                  <s-text variant="headingLg">
                    €{competitors.competitor_min?.toFixed(2)} – €
                    {competitors.competitor_max?.toFixed(2)}
                  </s-text>
                </div>
              </s-layout>

              <s-badge
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
                Position: {competitors.price_position} (
                {competitors.price_vs_avg_pct?.toFixed(1)}% vs. Ø)
              </s-badge>

              <s-index-table>
                {compDisplay.map((c, i) => (
                  <s-index-table-row key={c.url || i}>
                    <s-index-table-cell>#{i + 1} {c.title}</s-index-table-cell>
                    <s-index-table-cell>€{c.price}</s-index-table-cell>
                    <s-index-table-cell>{c.source}</s-index-table-cell>
                    <s-index-table-cell>
                      <s-badge
                        tone={
                          c.price < (competitors.current_price ?? 0)
                            ? 'critical'
                            : 'success'
                        }
                      >
                        {c.price < (competitors.current_price ?? 0)
                          ? `${(((c.price - (competitors.current_price ?? 0)) / (competitors.current_price ?? 1)) * 100).toFixed(1)}%`
                          : `+${(((c.price - (competitors.current_price ?? 0)) / (competitors.current_price ?? 1)) * 100).toFixed(1)}%`}
                      </s-badge>
                    </s-index-table-cell>
                  </s-index-table-row>
                ))}
              </s-index-table>
            </>
          ) : (
            <s-text tone="subdued">
              Noch keine Wettbewerbsdaten. Suche starten um Konkurrenten zu
              finden.
            </s-text>
          )}

          <s-button
            onClick={() => competitorSearchMutation.mutate()}
            loading={competitorSearchMutation.isPending}
          >
            {competitors?.has_data
              ? 'Wettbewerber aktualisieren'
              : 'Wettbewerber suchen (Serper)'}
          </s-button>
        </s-card>
      </s-layout>
    </s-page>
  );
}
