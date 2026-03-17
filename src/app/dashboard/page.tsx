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
    const steps = 28;
    const duration = 700;
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

function RevenueIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#059669" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 2v14M13 6c0-1.1-.9-2-2-2H7a2 2 0 0 0 0 4h4a2 2 0 0 1 0 4H6" />
    </svg>
  );
}

function PendingIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#d97706" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9" cy="9" r="7" />
      <path d="M9 5.5v4l2.5 1.5" />
    </svg>
  );
}

function AvgIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#4f46e5" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 13l4-5 4 3 4-7" />
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="#dc2626" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="7.5" cy="7.5" r="6" />
      <path d="M7.5 4.5v3.5M7.5 10h.01" />
    </svg>
  );
}

function TaskIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="#4f46e5" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2.5" y="2.5" width="10" height="10" rx="2" />
      <path d="M5 7.5l2 2 3-3" />
    </svg>
  );
}

function ArrowRight() {
  return (
    <svg className="piq-step-arr" width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M5 2.5l4 4.5-4 4.5" />
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
          <div className="piq-card">
            <div className="piq-loading">
              <s-spinner size="small" />
            </div>
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

        {/* ── Banner: ausstehende Empfehlungen ── */}
        {bannerVisible && pendingCount > 0 && (
          <s-banner
            tone="info"
            title={`${pendingCount} Preisempfehlungen ausstehend`}
            onDismiss={() => setBannerVisible(false)}
          >
            <s-stack direction="inline" gap="2" align-items="center">
              <s-paragraph>
                Durchschnittlich +€{avgPerProduct.toFixed(0)} Mehrumsatz pro Produkt möglich.
              </s-paragraph>
              <s-button variant="primary" size="slim" onClick={() => router.push(`/dashboard/pricing${suffix}`)}>
                Empfehlungen ansehen
              </s-button>
            </s-stack>
          </s-banner>
        )}

        {/* ── KPI Strip — 3 Cards ── */}
        <div className="piq-kpi">

          {/* Card 1: Mehrumsatz */}
          <div className="piq-kc piq-kc--green">
            <div className="piq-kc-icon piq-kc-icon--green">
              <RevenueIcon />
            </div>
            <div className="piq-kc-lbl">Möglicher Mehrumsatz</div>
            <div className="piq-kc-val">{revenueFormatted}</div>
            <div className="piq-kc-sub">{affectedCount} von {totalCount} Produkten optimierbar</div>
            <div className="piq-kc-prog">
              <div className="piq-kc-prog-row">
                <span>Fortschritt</span>
                <span>{Math.round(progressPct)}%</span>
              </div>
              <div className="piq-kc-bar">
                <div className="piq-kc-bar-fill" style={{ width: `${progressPct}%` }} />
              </div>
            </div>
          </div>

          {/* Card 2: Ausstehend */}
          <div className="piq-kc piq-kc--amber">
            <div className="piq-kc-icon piq-kc-icon--amber">
              <PendingIcon />
            </div>
            <div className="piq-kc-lbl">Ausstehend</div>
            <div className="piq-kc-val piq-kc-val--amber">
              <AnimatedNumber value={pendingCount} />
            </div>
            <div className="piq-kc-sub">offene Empfehlungen</div>
          </div>

          {/* Card 3: Ø pro Produkt */}
          <div className="piq-kc piq-kc--indigo">
            <div className="piq-kc-icon piq-kc-icon--indigo">
              <AvgIcon />
            </div>
            <div className="piq-kc-lbl">Ø pro Produkt</div>
            <div className="piq-kc-val piq-kc-val--indigo">
              €<AnimatedNumber value={Math.abs(Math.round(avgPerProduct))} />
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
                    <div className={`piq-step-ic ${step.urgent ? 'piq-step-ic--urgent' : 'piq-step-ic--normal'}`}>
                      {step.urgent ? <AlertIcon /> : <TaskIcon />}
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
