'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import { getDashboardStats, getRecommendationsList } from '@/lib/api';
import { FortschrittsCard } from '@/components/FortschrittsCard';
import { TopRecommendations } from '@/components/TopProductsChart';

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = React.useState(0);
  React.useEffect(() => {
    if (value === 0) { setDisplay(0); return; }
    const steps = 32;
    const duration = 800;
    const increment = value / steps;
    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= value) { setDisplay(value); clearInterval(timer); }
      else { setDisplay(Math.floor(current)); }
    }, duration / steps);
    return () => clearInterval(timer);
  }, [value]);
  return <>{display.toLocaleString('de-DE')}</>;
}

function useShopSuffix(): string {
  const searchParams = useSearchParams();
  const shop    = searchParams.get('shop')     ?? (typeof window !== 'undefined' ? localStorage.getItem('shop_domain')      : null) ?? '';
  const host    = searchParams.get('host')     ?? (typeof window !== 'undefined' ? localStorage.getItem('shopify_host')     : null) ?? '';
  const shopId  = searchParams.get('shop_id') ?? (typeof window !== 'undefined' ? localStorage.getItem('current_shop_id')  : null) ?? '';
  const idToken = searchParams.get('id_token') ?? '';
  const p = new URLSearchParams();
  if (shop)    p.set('shop',     shop);
  if (host)    p.set('host',     host);
  if (shopId)  p.set('shop_id',  shopId);
  if (idToken) p.set('id_token', idToken);
  const q = p.toString();
  return q ? `?${q}` : '';
}

function RevenueIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 19 19" fill="none" stroke="#059669" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.5 2v15M14 6.5c0-1.2-.9-2.2-2.2-2.2H7.5a2.2 2.2 0 0 0 0 4.4h4a2.2 2.2 0 0 1 0 4.4H6" />
    </svg>
  );
}

function PendingIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 19 19" fill="none" stroke="#d97706" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9.5" cy="9.5" r="7.5" />
      <path d="M9.5 5.5v4.5l3 1.5" />
    </svg>
  );
}

function AvgIcon() {
  return (
    <svg width="19" height="19" viewBox="0 0 19 19" fill="none" stroke="#4f46e5" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2.5 14l5-6 4.5 3.5 4.5-8" />
      <circle cx="16.5" cy="3.5" r="1.5" fill="#4f46e5" stroke="none" />
    </svg>
  );
}

function ArrowRight() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      <path d="M4 2l4 4-4 4" />
    </svg>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const suffix = useShopSuffix();

  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn:  getDashboardStats,
  });

  const { data: recsData } = useQuery({
    queryKey: ['recommendations-list', 'pending'],
    queryFn:  () => getRecommendationsList('pending'),
  });

  const pendingCount     = stats?.recommendations_pending ?? 0;
  const revenueAmount    = stats?.missed_revenue?.total ?? 0;
  const revenueRounded   = Math.abs(Math.round(revenueAmount));
  const avgPerProduct = stats?.missed_revenue?.avg_per_product ?? 0;
  const affectedCount = stats?.missed_revenue?.product_count ?? 0;
  const totalCount    = stats?.products_count ?? 1;
  const progressPct   = totalCount > 0 ? Math.min((affectedCount / totalCount) * 100, 100) : 0;

  if (isLoading) {
    return (
      <s-page title="Übersicht">
        <div className="piq-dashboard">
          <div className="piq-card">
            <div className="piq-loading"><s-spinner size="small" /></div>
          </div>
        </div>
      </s-page>
    );
  }

  if (error || !stats) {
    return (
      <s-page title="Übersicht">
        <div className="piq-dashboard">
          <s-banner tone="critical" title="Fehler beim Laden">
            <s-paragraph>
              Dashboard konnte nicht geladen werden.
              {error instanceof Error && ` (${error.message})`}
            </s-paragraph>
          </s-banner>
        </div>
      </s-page>
    );
  }

  return (
    <s-page title="Übersicht">
      <div className="piq-dashboard">

        {/* ══ 3 KPI-Cards ══ */}
        <div className="piq-hero-grid">

          {/* Card 1: Möglicher mehr Umsatz */}
          <div className="piq-hero-card">
            <div className="piq-hero-icon">
              <RevenueIcon />
            </div>
            <div className="piq-hero-lbl">Möglicher mehr Umsatz (monatlich)</div>
            <div className="piq-hero-val">+<AnimatedNumber value={revenueRounded} /> €</div>
            <div className="piq-hero-sub">
              {affectedCount} von {totalCount} Produkten optimierbar
            </div>
            <div className="piq-kc-prog piq-kc-prog--bottom">
              <div className="piq-kc-prog-row">
                <span>Optimierungsfortschritt</span>
                <span>{Math.round(progressPct)}%</span>
              </div>
              <div className="piq-kc-bar">
                <div className="piq-kc-bar-fill" style={{ width: `${progressPct}%` }} />
              </div>
            </div>
          </div>

          {/* Card 2: Ausstehende Empfehlungen */}
          <div className="piq-sat-card">
            <div className="piq-sat-icon">
              <PendingIcon />
            </div>
            <div className="piq-sat-lbl">Ausstehend</div>
            <div className="piq-sat-val">
              <AnimatedNumber value={pendingCount} />
            </div>
            <div className="piq-sat-sub">offene Empfehlungen warten auf Bearbeitung</div>
            <button
              className="piq-cta piq-cta--secondary"
              onClick={() => router.push(`/dashboard/pricing${suffix}`)}
            >
              Jetzt bearbeiten <ArrowRight />
            </button>
          </div>

          {/* Card 3: Ø mehr Umsatz pro Produkt */}
          <div className="piq-avg-card">
            <div className="piq-avg-icon">
              <AvgIcon />
            </div>
            <div className="piq-avg-lbl">Ø pro Produkt</div>
            <div className="piq-avg-val">
              <AnimatedNumber value={Math.abs(Math.round(avgPerProduct))} /> €
            </div>
            <div className="piq-avg-sub">möglicher mehr Umsatz je Produkt</div>
            <button
              className="piq-cta piq-cta--secondary"
              onClick={() => router.push(`/dashboard/products${suffix}`)}
            >
              Produkte ansehen <ArrowRight />
            </button>
          </div>

        </div>

        {/* ══ Top Empfehlungen ══ */}
        {(recsData?.recommendations?.length ?? 0) > 0 && (
          <div className="piq-chart-section">
            <div className="piq-chart-header">
              <div className="piq-chart-title">Top Empfehlungen</div>
              <span className="piq-chart-badge">
                {new Set(
                  recsData!.recommendations
                    .filter((r: { applied_at: string | null }) => r.applied_at == null)
                    .map((r: { product_id: number }) => r.product_id)
                ).size}{' '}
                Produkte
              </span>
            </div>
            <TopRecommendations
              recommendations={recsData!.recommendations}
              suffix={suffix}
            />
          </div>
        )}

        {/* ══ Fortschritt — volle Breite ══ */}
        <FortschrittsCard
          level={stats?.progress?.level ?? 'bronze'}
          points={stats?.progress?.points ?? 0}
          nextLevelPoints={stats?.progress?.next_level_points ?? 20}
          pointsNeeded={stats?.progress?.points_needed ?? 20}
          completedSteps={stats?.progress?.completed_steps ?? []}
          pendingSteps={stats?.progress?.pending_steps ?? []}
          hideQuickActions
        />

      </div>
    </s-page>
  );
}
