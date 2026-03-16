'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import { getDashboardStats } from '@/lib/api';
import { FortschrittsCard } from '@/components/FortschrittsCard';

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = React.useState(0);
  React.useEffect(() => {
    if (value === 0) { setDisplay(0); return; }
    const steps = 24;
    const duration = 600;
    const increment = value / steps;
    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= value) { setDisplay(value); clearInterval(timer); }
      else { setDisplay(Math.floor(current)); }
    }, duration / steps);
    return () => clearInterval(timer);
  }, [value]);
  return <>{display}</>;
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

function AlertIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#ef4444" strokeWidth="1.4" strokeLinecap="round">
      <circle cx="7" cy="7" r="5.5" />
      <path d="M7 4.5v3M7 9h.01" />
    </svg>
  );
}

function CostIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#3b82f6" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="10" height="9" rx="1.5" />
      <path d="M2 6h10M5 3V1M9 3V1" />
    </svg>
  );
}

function ArrowRight() {
  return (
    <svg className="piq-step-arr" width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="1.4">
      <path d="M4.5 2l4 4.5-4 4.5" />
    </svg>
  );
}

export default function DashboardPage() {
  const router  = useRouter();
  const suffix  = useShopSuffix();
  const [bannerVisible, setBannerVisible] = useState(true);

  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn:  getDashboardStats,
  });

  const pendingCount     = stats?.recommendations_pending ?? 0;
  const revenueAmount    = stats?.missed_revenue?.total ?? 0;
  const revenueFormatted = revenueAmount !== 0
    ? `+€${Math.abs(revenueAmount).toLocaleString('de-DE', { maximumFractionDigits: 0 })}`
    : '€0';
  const avgPerProduct  = stats?.missed_revenue?.avg_per_product ?? 0;
  const affectedCount  = stats?.missed_revenue?.product_count ?? 0;
  const totalCount     = stats?.products_count ?? 1;
  const progressPct    = totalCount > 0 ? Math.min((affectedCount / totalCount) * 100, 100) : 0;
  const nextStepsCount = stats?.next_steps?.length ?? 0;

  if (isLoading) {
    return (
      <s-page title="Übersicht">
        <div className="piq-dashboard">
          <div className="piq-card" style={{ padding: '32px 24px' }}>
            <div className="piq-loading">Lade Dashboard…</div>
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

        {/* ── Topbar-Benachrichtigung ── */}
        {bannerVisible && pendingCount > 0 && (
          <div className="piq-topbar">
            <div className="piq-topbar-pip" />
            <div className="piq-topbar-txt">
              <strong>{pendingCount} Preisempfehlungen ausstehend</strong>
              {' '}— Durchschnittlich +€{avgPerProduct.toFixed(0)} Mehrumsatz pro Produkt möglich.
            </div>
            <button className="piq-topbar-btn" onClick={() => router.push(`/dashboard/pricing${suffix}`)}>
              Ansehen →
            </button>
            <button className="piq-topbar-x" onClick={() => setBannerVisible(false)}>✕</button>
          </div>
        )}

        {/* ── KPI-Strip ── */}
        <div className="piq-kpi">
          <div className="piq-kc">
            <span className="piq-kc-badge piq-kc-badge--green">Aktiv</span>
            <div className="piq-kc-lbl">Möglicher Mehrumsatz</div>
            <div className="piq-kc-val">{revenueFormatted}</div>
            <div className="piq-kc-bar-wrap">
              <div className="piq-kc-bar-row">
                <span>{affectedCount} von {totalCount} Produkten</span>
                <span>{Math.round(progressPct)}%</span>
              </div>
              <div className="piq-kc-bar">
                <div className="piq-kc-bar-fill" style={{ width: `${progressPct}%` }} />
              </div>
            </div>
          </div>

          <div className="piq-kc">
            <div className="piq-kc-lbl">Ausstehend</div>
            <div className="piq-kc-val piq-kc-val--sm piq-kc-val--amber">
              <AnimatedNumber value={pendingCount} />
            </div>
            <div className="piq-kc-sub">offene Empfehlungen</div>
          </div>

          <div className="piq-kc">
            <div className="piq-kc-lbl">Ø pro Produkt</div>
            <div className="piq-kc-val piq-kc-val--sm">
              €{avgPerProduct.toFixed(0)}
            </div>
            <div className="piq-kc-sub">möglicher Mehrumsatz</div>
          </div>
        </div>

        {/* ── Unteres Grid ── */}
        <div className={`piq-lower${!nextStepsCount ? ' piq-lower--single' : ''}`}>

          {/* Nächste Schritte */}
          {nextStepsCount > 0 && (
            <div className="piq-card">
              <div className="piq-card-head">
                <div className="piq-card-ttl">Nächste Schritte</div>
                <div className="piq-card-meta">{nextStepsCount} ausstehend</div>
              </div>
              <div className="piq-card-body">
                {stats.next_steps!.slice(0, 4).map((step, i) => (
                  <div
                    key={i}
                    className="piq-step"
                    onClick={() => router.push(`${step.href}${suffix}`)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && router.push(`${step.href}${suffix}`)}
                  >
                    <div className="piq-step-ic">
                      {step.urgent ? <AlertIcon /> : <CostIcon />}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="piq-step-ttl">{step.title}</div>
                      <div className="piq-step-dsc">{step.description}</div>
                    </div>
                    <ArrowRight />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Fortschritt + Schnellaktionen */}
          <FortschrittsCard
            level={stats?.progress?.level ?? 'bronze'}
            points={stats?.progress?.points ?? 0}
            nextLevelPoints={stats?.progress?.next_level_points ?? 20}
            pointsNeeded={stats?.progress?.points_needed ?? 20}
            completedSteps={stats?.progress?.completed_steps ?? []}
            pendingSteps={stats?.progress?.pending_steps ?? []}
            onPriceAction={() => router.push(`/dashboard/pricing${suffix}`)}
            onProductsAction={() => router.push(`/dashboard/products${suffix}`)}
            onSettingsAction={() => router.push(`/dashboard/settings${suffix}`)}
          />

        </div>
      </div>
    </s-page>
  );
}
