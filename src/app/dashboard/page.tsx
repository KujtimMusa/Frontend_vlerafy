'use client';

import React from 'react';
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

export default function DashboardPage() {
  const router = useRouter();
  const suffix = useShopSuffix();

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
      <div className="vlerafy-main">
        <s-section>
          <s-stack direction="block" gap="4">
            <s-paragraph tone="subdued">Lade Dashboard...</s-paragraph>
          </s-stack>
        </s-section>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="vlerafy-main">
        <s-banner tone="critical" title="Fehler beim Laden">
          Dashboard konnte nicht geladen werden.
          {error instanceof Error && ` (${error.message})`}
        </s-banner>
      </div>
    );
  }

  const affectedCount = stats?.missed_revenue?.product_count ?? 0;
  const totalCount = stats?.products_count ?? 1;
  const progressPct = Math.min((affectedCount / totalCount) * 100, 100);

  return (
    <div className="vlerafy-main">
      {/* Notification Banner – Polaris Banner mit tone="warning" */}
      {pendingCount > 0 && (
        <s-banner
          tone="warning"
          title={`${pendingCount} Preisempfehlungen ausstehend`}
        >
          <s-stack direction="block" gap="2">
            <s-paragraph>
              Durchschnittlich +€{avgPerProduct.toFixed(0)} Mehrumsatz pro Produkt möglich.
            </s-paragraph>
            <s-button variant="primary" size="slim" onClick={handleViewRecommendations}>
              Jetzt ansehen
            </s-button>
          </s-stack>
        </s-banner>
      )}

      {/* Page Header */}
      <div className="vlerafy-page-header">
        <h1 className="vlerafy-page-title">Dashboard</h1>
        <p className="vlerafy-page-subtitle">Pricing Intelligence Übersicht</p>
      </div>

      {/* KPI Hero + Stats Grid */}
      <div className="priceiq-stats-grid">
        {/* KPI Hero – Möglicher Mehrumsatz */}
        <div className="priceiq-kpi-hero">
          <s-paragraph tone="subdued">
            <span
              style={{
                color: 'rgba(255,255,255,0.5)',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                fontSize: '11px',
              }}
            >
              Möglicher Mehrumsatz
            </span>
          </s-paragraph>
          <div className="priceiq-kpi-number">{revenueFormatted}</div>
          <s-stack direction="inline" gap="2" style={{ flexWrap: 'wrap', gap: '8px' }}>
            <s-badge tone="info">{stats?.missed_revenue?.recommendation_count ?? 0} Empfehlungen</s-badge>
            <span className="priceiq-kpi-delta">
              Ø +€{avgPerProduct.toFixed(0)} pro Produkt
            </span>
          </s-stack>
          <div style={{ marginTop: 16 }}>
            <div className="priceiq-progress-track">
              <div
                className="priceiq-progress-fill"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <s-paragraph tone="subdued">
              <span style={{ color: 'rgba(255,255,255,0.5)', fontSize: '12px' }}>
                {affectedCount} von {totalCount} Produkten betroffen
              </span>
            </s-paragraph>
          </div>
        </div>

        {/* Stat Cards – Polaris s-section mit priceiq-stat-card wrapper */}
        <div className="priceiq-stat-card">
          <s-section>
            <s-stack direction="block" gap="2">
              <s-paragraph tone="subdued">Produkte</s-paragraph>
              <s-heading size="2xl">
                <AnimatedNumber value={stats?.products_count ?? 0} />
              </s-heading>
              <s-paragraph tone="subdued">
                {stats?.products_with_recommendations ?? 0} mit Empfehlung
              </s-paragraph>
            </s-stack>
          </s-section>
        </div>

        <div className="priceiq-stat-card priceiq-stat-card--warning">
          <s-section>
            <s-stack direction="block" gap="2">
              <s-paragraph tone="subdued">Ausstehend</s-paragraph>
              <s-heading size="2xl">
                <AnimatedNumber value={stats?.recommendations_pending ?? 0} />
              </s-heading>
              <s-paragraph tone="subdued">offene Preisempfehlungen</s-paragraph>
            </s-stack>
          </s-section>
        </div>

        <div className="priceiq-stat-card priceiq-stat-card--success">
          <s-section>
            <s-stack direction="block" gap="2">
              <s-paragraph tone="subdued">Umgesetzt</s-paragraph>
              <s-heading size="2xl">
                <AnimatedNumber value={stats?.recommendations_applied ?? 0} />
              </s-heading>
              <s-paragraph tone="subdued">Empfehlungen angewandt</s-paragraph>
            </s-stack>
          </s-section>
        </div>
      </div>

      {/* Nächste Schritte + Fortschritt */}
      <div
        className={`priceiq-lower-grid ${
          !stats?.next_steps?.length ? 'priceiq-lower-grid--single' : ''
        }`}
      >
        {/* Nächste Schritte Card */}
        {stats?.next_steps && stats.next_steps.length > 0 && (
          <s-section>
            <s-stack direction="block" gap="4">
              <s-heading size="md">Nächste Schritte</s-heading>
              {stats.next_steps.slice(0, 3).map((step, i) => (
                <Link
                  key={i}
                  href={`${step.href}${suffix}`}
                  className="priceiq-next-step-item"
                >
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: '50%',
                      background: step.urgent ? 'rgba(239, 68, 68, 0.1)' : 'var(--v-navy-50)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                      fontSize: '16px',
                    }}
                  >
                    {step.urgent ? '🔥' : '📊'}
                  </div>
                  <s-stack direction="block" gap="0" style={{ flex: 1 }}>
                    <s-stack direction="inline" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                      <p style={{ fontWeight: 600, fontSize: 13, margin: 0, color: 'var(--v-gray-950)' }}>{step.title}</p>
                      <span style={{ color: 'var(--v-gray-400)', fontSize: 14 }}>→</span>
                    </s-stack>
                    <s-paragraph tone="subdued">{step.description}</s-paragraph>
                  </s-stack>
                </Link>
              ))}
            </s-stack>
          </s-section>
        )}

        {/* Fortschritt + Schnellaktionen */}
        <s-stack direction="block" gap="4">
          <FortschrittsCard
            level={stats?.progress?.level ?? 'bronze'}
            points={stats?.progress?.points ?? 0}
            nextLevelPoints={stats?.progress?.next_level_points ?? 20}
            pointsNeeded={stats?.progress?.points_needed ?? 20}
            completedSteps={stats?.progress?.completed_steps ?? []}
            pendingSteps={stats?.progress?.pending_steps ?? []}
          />
          {/* Schnellaktionen inline unter Fortschritt */}
          <s-section>
            <s-stack direction="block" gap="3">
              <s-heading size="md">Schnellaktionen</s-heading>
              <s-stack direction="block" gap="2">
                <s-button
                  variant="secondary"
                  size="slim"
                  onClick={() => router.push(`/dashboard/pricing${suffix}`)}
                  style={{ width: '100%', justifyContent: 'flex-start' }}
                >
                  ⚡ Preise optimieren
                </s-button>
                <s-button
                  variant="secondary"
                  size="slim"
                  onClick={() => router.push(`/dashboard/products${suffix}`)}
                  style={{ width: '100%', justifyContent: 'flex-start' }}
                >
                  📦 Produkte sync
                </s-button>
                <s-button
                  variant="secondary"
                  size="slim"
                  onClick={() => router.push(`/dashboard/settings${suffix}`)}
                  style={{ width: '100%', justifyContent: 'flex-start' }}
                >
                  ⚙️ Einstellungen
                </s-button>
              </s-stack>
            </s-stack>
          </s-section>
        </s-stack>
      </div>
    </div>
  );
}
