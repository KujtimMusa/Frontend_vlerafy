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

function PriceActionIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#059669" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 1v14M11 5c0-1-.9-1.8-1.8-1.8H6.5a1.8 1.8 0 0 0 0 3.6h3a1.8 1.8 0 0 1 0 3.6H5" />
    </svg>
  );
}

function ProductActionIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#d97706" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2.5 2.5h2.5l2 8.5h6.5l1.3-5.5H5.5" />
      <circle cx="8" cy="14" r="1" />
      <circle cx="12.5" cy="14" r="1" />
    </svg>
  );
}

function SettingsActionIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#6b7280" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8" cy="8" r="2.5" />
      <path d="M8 1v1.5M8 13.5V15M1 8h1.5M13.5 8H15M3 3l1 1M12 12l1 1M3 13l1-1M12 4l1-1" />
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

  /* ── Loading ── */
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

  /* ── Error ── */
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
                Durchschnittlich +€{Math.abs(Math.round(avgPerProduct))} Mehrumsatz pro Produkt möglich.
              </div>
            </div>
            <div className="piq-notice-actions">
              <s-button variant="primary" size="slim" onClick={() => router.push(`/dashboard/pricing${suffix}`)}>
                Empfehlungen ansehen
              </s-button>
              <button className="piq-notice-dismiss" onClick={() => setNoticeVisible(false)} aria-label="Schließen">
                ×
              </button>
            </div>
          </div>
        )}

        {/* ══ ZEILE 2: Hero (2/3) + Satellit Ausstehend (1/3) ══ */}
        <div className="piq-hero-grid">

          {/* Hero: Möglicher Mehrumsatz */}
          <div className="piq-hero-card">
            <div className="piq-hero-top">
              <s-badge tone="success">Aktiv</s-badge>
            </div>
            <div className="piq-hero-lbl">Möglicher Mehrumsatz</div>
            <div className="piq-hero-val">{revenueFormatted}</div>
            <div className="piq-hero-sub">
              <div className="piq-hero-sub-item">
                <div className="piq-hero-sub-dot" />
                <span>{affectedCount} von {totalCount} Produkten optimierbar</span>
              </div>
              <div className="piq-hero-sub-item">
                <div className="piq-hero-sub-dot" style={{ background: 'var(--indigo)' }} />
                <span>Ø €{Math.abs(Math.round(avgPerProduct))} pro Produkt</span>
              </div>
            </div>
            <div className="piq-kc-prog" style={{ marginTop: 'auto' }}>
              <div className="piq-kc-prog-row">
                <span>Optimierungsfortschritt</span>
                <span>{Math.round(progressPct)}%</span>
              </div>
              <div className="piq-kc-bar">
                <div className="piq-kc-bar-fill" style={{ width: `${progressPct}%` }} />
              </div>
            </div>
          </div>

          {/* Satellit: Ausstehend */}
          <div className="piq-sat-card">
            <div className="piq-sat-icon">
              <PendingIcon />
            </div>
            <div className="piq-sat-lbl">Ausstehend</div>
            <div className="piq-sat-val">
              <AnimatedNumber value={pendingCount} />
            </div>
            <div className="piq-sat-sub">offene Empfehlungen warten auf Bearbeitung</div>
            <s-button
              variant="primary"
              size="slim"
              onClick={() => router.push(`/dashboard/pricing${suffix}`)}
            >
              Jetzt bearbeiten
            </s-button>
          </div>

        </div>

        {/* ══ ZEILE 3: Nächste Schritte — volle Breite, 2-Spalten mit CTAs ══ */}
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
                    <div className={`piq-step-ic ${step.urgent ? 'piq-step-ic--urgent' : 'piq-step-ic--normal'}`} style={{ flexShrink: 0 }}>
                      {step.urgent ? <AlertIcon /> : <TaskIcon />}
                    </div>
                    <div className="piq-step-row-body">
                      <div className="piq-step-row-ttl">{step.title}</div>
                      <div className="piq-step-row-dsc">{step.description}</div>
                    </div>
                    <s-button
                      variant={step.urgent ? 'primary' : 'secondary'}
                      size="slim"
                      onClick={() => router.push(`${step.href}${suffix}`)}
                    >
                      {step.urgent ? 'Jetzt umsetzen' : 'Öffnen'}
                    </s-button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ══ ZEILE 4: Fortschritt (2/3) + Schnellaktionen (1/3) ══ */}
        <div className="piq-bottom-grid">

          {/* Fortschritt – ohne Quick Actions (werden rechts separat gezeigt) */}
          <FortschrittsCard
            level={stats?.progress?.level ?? 'bronze'}
            points={stats?.progress?.points ?? 0}
            nextLevelPoints={stats?.progress?.next_level_points ?? 20}
            pointsNeeded={stats?.progress?.points_needed ?? 20}
            completedSteps={stats?.progress?.completed_steps ?? []}
            pendingSteps={stats?.progress?.pending_steps ?? []}
            hideQuickActions
          />

          {/* Schnellaktionen — volle Breite, vertikal gestapelt */}
          <div className="piq-qa-section">
            <div className="piq-card-head">
              <div className="piq-card-ttl">Schnellaktionen</div>
            </div>
            <div className="piq-qa-vert">
              <s-button variant="secondary" onClick={() => router.push(`/dashboard/pricing${suffix}`)}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <PriceActionIcon />
                  Preise optimieren
                </span>
              </s-button>
              <s-button variant="secondary" onClick={() => router.push(`/dashboard/products${suffix}`)}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <ProductActionIcon />
                  Produkte synchronisieren
                </span>
              </s-button>
              <s-button variant="secondary" onClick={() => router.push(`/dashboard/settings${suffix}`)}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <SettingsActionIcon />
                  Einstellungen
                </span>
              </s-button>
            </div>
          </div>

        </div>
      </div>
    </s-page>
  );
}
