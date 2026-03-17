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

function AlertIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="#dc2626" strokeWidth="1.6" strokeLinecap="round">
      <circle cx="7.5" cy="7.5" r="6" />
      <path d="M7.5 4.5v3.5M7.5 10.2h.01" />
    </svg>
  );
}

function TaskIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="#4f46e5" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2.5" y="2.5" width="10" height="10" rx="2.5" />
      <path d="M5 7.5l2 2 3-3" />
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
  const router  = useRouter();
  const suffix  = useShopSuffix();
  const [noticeVisible, setNoticeVisible] = useState(true);

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

        {/* ══ ZEILE 1: Notification Banner ══ */}
        {noticeVisible && pendingCount > 0 && (
          <div className="piq-notice" role="status">
            <div className="piq-notice-pip" aria-hidden="true" />
            <div className="piq-notice-body">
              <div className="piq-notice-title">
                {pendingCount} Preisempfehlungen ausstehend
              </div>
              <div className="piq-notice-sub">
                Durchschnittlich +€{Math.abs(Math.round(avgPerProduct))} mehr Umsatz pro Produkt möglich.
              </div>
            </div>
            <div className="piq-notice-actions">
              <button
                className="piq-cta piq-cta--primary piq-cta--sm"
                onClick={() => router.push(`/dashboard/pricing${suffix}`)}
              >
                Empfehlungen ansehen <ArrowRight />
              </button>
              <button
                className="piq-notice-dismiss"
                onClick={() => setNoticeVisible(false)}
                aria-label="Schließen"
              >
                ×
              </button>
            </div>
          </div>
        )}

        {/* ══ ZEILE 2: 3 KPI-Cards ══ */}
        <div className="piq-hero-grid">

          {/* Card 1: Möglicher mehr Umsatz */}
          <div className="piq-hero-card">
            <div className="piq-hero-top">
              <s-badge tone="success">Aktiv</s-badge>
            </div>
            <div className="piq-hero-lbl">Möglicher mehr Umsatz (monatlich)</div>
            <div className="piq-hero-val">{revenueFormatted}</div>
            <div className="piq-hero-sub">
              <div className="piq-hero-sub-item">
                <div className="piq-hero-sub-dot" />
                <span>{affectedCount} von {totalCount} Produkten optimierbar</span>
              </div>
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
              className="piq-cta piq-cta--primary"
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
              €<AnimatedNumber value={Math.abs(Math.round(avgPerProduct))} />
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

        {/* ══ ZEILE 3: Nächste Schritte ══ */}
        {nextStepsCount > 0 && (
          <div className="piq-card">
            <div className="piq-card-head">
              <div className="piq-card-ttl">Nächste Schritte</div>
              <s-badge tone={stats.next_steps!.some((s) => s.urgent) ? 'critical' : 'attention'}>
                {nextStepsCount} ausstehend
              </s-badge>
            </div>
            <div className="piq-card-body">
              <div className="piq-steps-grid">
                {stats.next_steps!.slice(0, 4).map((step, i) => (
                  <div key={i} className="piq-step-row">
                    <div className={`piq-step-ic ${step.urgent ? 'piq-step-ic--urgent' : 'piq-step-ic--normal'}`}>
                      {step.urgent ? <AlertIcon /> : <TaskIcon />}
                    </div>
                    <div className="piq-step-row-body">
                      <div className="piq-step-row-ttl">{step.title}</div>
                      <div className="piq-step-row-dsc">{step.description}</div>
                    </div>
                    <button
                      className={`piq-cta ${step.urgent ? 'piq-cta--primary' : 'piq-cta--secondary'} piq-cta--sm`}
                      onClick={() => router.push(`${step.href}${suffix}`)}
                    >
                      {step.urgent ? 'Jetzt umsetzen' : 'Öffnen'} <ArrowRight />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ══ ZEILE 4: Fortschritt — volle Breite ══ */}
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
