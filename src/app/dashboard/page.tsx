/*
 * ANALYSE-ERGEBNIS:
 * - Kein Polaris Page/Layout (Projekt nutzt Web Components s-box/s-stack)
 * - Custom-CSS nur auf eigenen piq-* Wrappern, keine .Polaris-* Overrides
 * - Abgeschnittene Elemente: behoben durch white-space: nowrap auf .piq-kc-val
 * - KPI-Strip: border-right zwischen Zellen, Grid mit fr-Einheiten
 * - Light Mode Tokens in :root definiert
 */

'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import { getDashboardStats } from '@/lib/api';
import { FortschrittsCard } from '@/components/FortschrittsCard';

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = React.useState(0);
  React.useEffect(() => {
    if (value === 0) {
      setDisplay(0);
      return;
    }
    const steps = 24;
    const duration = 600;
    const increment = value / steps;
    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= value) {
        setDisplay(value);
        clearInterval(timer);
      } else {
        setDisplay(Math.floor(current));
      }
    }, duration / steps);
    return () => clearInterval(timer);
  }, [value]);
  return <>{display}</>;
}

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
  const q = p.toString();
  return q ? `?${q}` : '';
}

function AlertIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="var(--red)" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="7" cy="7" r="5.5" />
      <path d="M7 4.5v3M7 9.5h.01" />
    </svg>
  );
}

function CostIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="var(--blue)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="10" height="9" rx="1.5" />
      <path d="M2 6h10M5 3V1M9 3V1" />
    </svg>
  );
}

function PriceIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M4 2v10M10 4v10M2 6h4M8 4h4" strokeLinecap="round" />
    </svg>
  );
}

function SyncIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M2 7a5 5 0 019-2.5M12 7a5 5 0 01-9 2.5M2 7h3v3M12 7H9V4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="7" cy="7" r="2.5" />
      <path d="M7 1v2M7 11v2M1 7h2M11 7h2M2.34 2.34l1.42 1.42M10.24 10.24l1.42 1.42M2.34 11.66l1.42-1.42M10.24 3.76l1.42-1.42" strokeLinecap="round" />
    </svg>
  );
}

function ChevronIcon() {
  return (
    <svg className="piq-step-arr" width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M4.5 2l4 4.5-4 4.5" />
    </svg>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const suffix = useShopSuffix();
  const [bannerVisible, setBannerVisible] = useState(true);

  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });

  const pendingCount = stats?.recommendations_pending ?? 0;
  const revenueAmount = stats?.missed_revenue?.total ?? 0;
  const revenueFormatted =
    revenueAmount !== 0
      ? `+€${Math.abs(revenueAmount).toLocaleString('de-DE', { maximumFractionDigits: 0 })}`
      : '€0';
  const avgPerProduct = stats?.missed_revenue?.avg_per_product ?? 0;

  const handleViewRecommendations = () => {
    router.push(`/dashboard/pricing${suffix}`);
  };

  if (isLoading) {
    return (
      <div className="piq-dashboard">
        <p className="piq-loading">Lade Dashboard...</p>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="piq-dashboard">
        <div className="piq-topbar" style={{ borderLeftColor: 'var(--red)' }}>
          <p className="piq-topbar-txt">
            <strong>Fehler beim Laden</strong>
            {error instanceof Error && ` — ${error.message}`}
          </p>
        </div>
      </div>
    );
  }

  const affectedCount = stats?.missed_revenue?.product_count ?? 0;
  const totalCount = stats?.products_count ?? 1;
  const progressPct = totalCount > 0 ? Math.min((affectedCount / totalCount) * 100, 100) : 0;

  const nextStepsCount = stats?.next_steps?.length ?? 0;

  return (
    <div className="piq-dashboard">
      {/* Topbar Banner */}
      {bannerVisible && pendingCount > 0 && (
        <div className="piq-topbar">
          <div className="piq-topbar-pip" />
          <p className="piq-topbar-txt">
            <strong>{pendingCount} Preisempfehlungen ausstehend</strong>
            {' '}— Durchschnittlich +€{avgPerProduct.toFixed(0)} Mehrumsatz pro Produkt möglich.
          </p>
          <button className="piq-topbar-btn" onClick={handleViewRecommendations}>
            Jetzt ansehen →
          </button>
          <button className="piq-topbar-x" onClick={() => setBannerVisible(false)} aria-label="Schließen">✕</button>
        </div>
      )}

      {/* KPI Strip */}
      <div className="piq-kpi">
        <div className="piq-kc piq-kc--main">
          <span className="piq-kc-badge piq-kc-badge--green">Aktiv</span>
          <div className="piq-kc-lbl">Möglicher Mehrumsatz</div>
          <div className="piq-kc-val">{revenueFormatted}</div>
          <div className="piq-kc-bar-wrap">
            <div className="piq-kc-bar-row">
              <span>{affectedCount} von {totalCount} Produkten betroffen</span>
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
          <div className="piq-kc-val piq-kc-val--sm">€{avgPerProduct.toFixed(0)}</div>
          <div className="piq-kc-sub">möglicher Mehrumsatz</div>
        </div>
      </div>

      {/* Lower Grid */}
      <div className={`piq-lower ${!nextStepsCount ? 'piq-lower--single' : ''}`}>
        {nextStepsCount > 0 && (
          <div className="piq-card">
            <div className="piq-card-head">
              <div className="piq-card-ttl">Nächste Schritte</div>
              <div className="piq-card-meta">{nextStepsCount} ausstehend</div>
            </div>
            <div className="piq-card-body">
              {stats.next_steps!.slice(0, 4).map((step, i) => (
                <Link
                  key={i}
                  href={`${step.href}${suffix}`}
                  className="piq-step"
                  style={{ textDecoration: 'none', color: 'inherit' }}
                >
                  <div className="piq-step-ic">
                    {step.urgent ? <AlertIcon /> : <CostIcon />}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="piq-step-ttl">{step.title}</div>
                    <div className="piq-step-dsc">{step.description}</div>
                  </div>
                  <ChevronIcon />
                </Link>
              ))}
            </div>
          </div>
        )}

        <div className="piq-card piq-progress-card">
          <FortschrittsCard
            level={stats?.progress?.level ?? 'bronze'}
            points={stats?.progress?.points ?? 0}
            nextLevelPoints={stats?.progress?.next_level_points ?? 20}
            pointsNeeded={stats?.progress?.points_needed ?? 20}
            completedSteps={stats?.progress?.completed_steps ?? []}
            pendingSteps={stats?.progress?.pending_steps ?? []}
          />
          <div className="piq-qa-wrap">
            <div className="piq-qa-lbl">Schnellaktionen</div>
            <div className="piq-qa-grid">
              <button type="button" className="piq-qa-btn" onClick={() => router.push(`/dashboard/pricing${suffix}`)}>
                <PriceIcon /> Preise
              </button>
              <button type="button" className="piq-qa-btn" onClick={() => router.push(`/dashboard/products${suffix}`)}>
                <SyncIcon /> Sync
              </button>
              <button type="button" className="piq-qa-btn" onClick={() => router.push(`/dashboard/settings${suffix}`)}>
                <SettingsIcon /> Einstellungen
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
