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
          <span
            key={i}
            className={`piq-conf-dot${i < filled ? ' piq-conf-dot--filled' : ''}`}
          />
        ))}
      </div>
      <span className="piq-conf-pct">{pct}%</span>
    </div>
  );
}

const truncate = (s: string, max = 28) =>
  s.length > max ? s.slice(0, max) + '…' : s;

const strategyLabel: Record<string, string> = {
  demand_pricing: 'Nachfrage',
  competitive_pricing: 'Wettbewerb',
  margin_optimization: 'Marge',
  inventory_clearance: 'Abverkauf',
  premium_pricing: 'Premium',
  psychological_pricing: 'Psycho-Preis',
};

export function TopRecommendations({ recommendations, suffix = '' }: TopRecommendationsProps) {
  const router = useRouter();

  const pending = recommendations
    .filter((r) => r.applied_at == null)
    .map((r) => {
      const diff = r.recommended_price - r.current_price;
      return { ...r, diff, absDiff: Math.abs(diff) };
    })
    .sort((a, b) => b.absDiff - a.absDiff)
    .slice(0, 5);

  if (pending.length === 0) {
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
      {pending.map((rec, idx) => {
        const isUp = rec.diff > 0;
        const changePct = rec.current_price > 0
          ? ((rec.diff / rec.current_price) * 100).toFixed(1)
          : '0';
        const label = strategyLabel[rec.strategy] ?? rec.strategy;

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

            {/* Price: current → recommended */}
            <div className="piq-toprec-prices">
              <span className="piq-toprec-cur">
                {rec.current_price.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €
              </span>
              <span className="piq-toprec-arrow">→</span>
              <span className={`piq-toprec-rec${isUp ? ' piq-toprec-rec--up' : ' piq-toprec-rec--down'}`}>
                {rec.recommended_price.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €
              </span>
            </div>

            {/* Change badge */}
            <div className={`piq-toprec-change${isUp ? ' piq-toprec-change--up' : ' piq-toprec-change--down'}`}>
              {isUp ? '↑' : '↓'} {changePct}%
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
