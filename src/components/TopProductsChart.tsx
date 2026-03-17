'use client';

import React from 'react';
import { useRouter } from 'next/navigation';

interface Recommendation {
  product_id: number;
  product_name: string;
  recommended_price: number;
  current_price: number;
  confidence: number;
  strategy: string;
  applied_at: string | null;
  sales_30d?: number | null;
  sales_7d?: number | null;
}

interface TopRecommendationsProps {
  recommendations: Recommendation[];
  suffix?: string;
}

function ArrowRight() {
  return (
    <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      <path d="M3.5 2l4 3.5-4 3.5" />
    </svg>
  );
}

function ConfidenceDots({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const filled = Math.round(value * 5);
  return (
    <div className="piq-conf-wrap" title={`${pct}% Konfidenz`}>
      <div className="piq-conf-dots">
        {[0, 1, 2, 3, 4].map((i) => (
          <span key={i} className={`piq-conf-dot${i < filled ? ' piq-conf-dot--filled' : ''}`} />
        ))}
      </div>
      <span className="piq-conf-pct">{pct}%</span>
    </div>
  );
}

const truncate = (s: string, max = 30) =>
  s.length > max ? s.slice(0, max) + '…' : s;

const strategyLabel: Record<string, string> = {
  demand_pricing: 'Nachfrage',
  demand_inventory_signal: 'Nachfrage-Signal',
  competitive_pricing: 'Wettbewerb',
  margin_optimization: 'Marge',
  inventory_clearance: 'Abverkauf',
  inventory_normal_no_sales: 'Lager-Optimierung',
  premium_pricing: 'Premium',
  psychological_pricing: 'Psycho-Preis',
  ML_OPTIMIZED_CONSTRAINED: 'KI-optimiert',
  ml_optimized: 'KI-optimiert',
};

function readableStrategy(raw: string): string {
  if (strategyLabel[raw]) return strategyLabel[raw];
  return raw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function monthlyPotential(rec: Recommendation): number {
  const diff = rec.recommended_price - rec.current_price;
  if (rec.sales_30d && rec.sales_30d > 0) return rec.sales_30d * diff;
  if (rec.sales_7d && rec.sales_7d > 0) return (rec.sales_7d / 7) * 30 * diff;
  return 5 * diff;
}

export function TopRecommendations({ recommendations, suffix = '' }: TopRecommendationsProps) {
  const router = useRouter();

  const pending = recommendations.filter((r) => r.applied_at == null);

  // Deduplizieren: nur eine Empfehlung pro Produkt (höchstes absolutes Monatspotenzial)
  const byProduct = new Map<number, Recommendation & { monthly: number }>();
  for (const r of pending) {
    const monthly = monthlyPotential(r);
    const existing = byProduct.get(r.product_id);
    if (!existing || Math.abs(monthly) > Math.abs(existing.monthly)) {
      byProduct.set(r.product_id, { ...r, monthly });
    }
  }

  const top5 = Array.from(byProduct.values())
    .sort((a, b) => Math.abs(b.monthly) - Math.abs(a.monthly))
    .slice(0, 5);

  if (top5.length === 0) {
    return (
      <div className="piq-toprec-empty">
        <div className="piq-toprec-empty-title">Keine offenen Empfehlungen</div>
        <div className="piq-toprec-empty-sub">
          Generiere Empfehlungen für deine Produkte um hier ein Ranking zu sehen.
        </div>
      </div>
    );
  }

  return (
    <div className="piq-toprec-list">
      {top5.map((rec, idx) => {
        const isPositive = rec.monthly > 0;
        const monthlyAbs = Math.abs(rec.monthly);
        const label = readableStrategy(rec.strategy);

        return (
          <div
            key={rec.product_id}
            className="piq-toprec-row"
            tabIndex={0}
            role="button"
            onClick={() => router.push(`/dashboard/products/${rec.product_id}${suffix}`)}
            onKeyDown={(e) => e.key === 'Enter' && router.push(`/dashboard/products/${rec.product_id}${suffix}`)}
          >
            {/* Rank */}
            <div className="piq-toprec-rank">{idx + 1}</div>

            {/* Product + Strategy */}
            <div className="piq-toprec-info">
              <div className="piq-toprec-name">{truncate(rec.product_name)}</div>
              <div className="piq-toprec-strat">{label}</div>
            </div>

            {/* Monthly Potential */}
            <div className={`piq-toprec-monthly${isPositive ? ' piq-toprec-monthly--up' : ' piq-toprec-monthly--down'}`}>
              <span className="piq-toprec-monthly-val">
                {isPositive ? '+' : '-'}€{monthlyAbs.toLocaleString('de-DE', { maximumFractionDigits: 0 })}
              </span>
              <span className="piq-toprec-monthly-lbl">/ Monat</span>
            </div>

            {/* Confidence */}
            <ConfidenceDots value={rec.confidence} />

            {/* Arrow */}
            <div className="piq-toprec-go"><ArrowRight /></div>
          </div>
        );
      })}
    </div>
  );
}
