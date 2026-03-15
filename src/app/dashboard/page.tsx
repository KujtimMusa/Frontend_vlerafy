'use client';

import React from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import { getDashboardStats } from '@/lib/api';
import { FortschrittsCard } from '@/components/FortschrittsCard';

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = React.useState(0);
  React.useEffect(() => {
    const duration = 800;
    const steps = 30;
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
  const suffix = useShopSuffix();

  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });

  const syncedProducts = stats?.products_count ?? 0;
  const pendingCount = stats?.recommendations_pending ?? 0;
  const revenue = stats?.missed_revenue?.total != null
    ? `+€${Math.abs(stats.missed_revenue.total).toLocaleString('de-DE', { maximumFractionDigits: 0 })}`
    : '€0';
  const appliedCount = stats?.recommendations_applied ?? 0;

  if (isLoading) {
    return (
      <div className="vlerafy-main">
        <div style={{ padding: 24, background: 'var(--v-white)', borderRadius: 'var(--v-radius-md)' }}>
          Lade Dashboard...
        </div>
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

  return (
    <div className="vlerafy-main">
      <s-stack direction="block" gap="0">
        <div className="vlerafy-page-header" style={{ marginBottom: 28 }}>
          <s-stack direction="inline" align-items="center" justify-content="space-between">
            <div>
              <h1 className="vlerafy-page-title">Dashboard</h1>
              <p className="vlerafy-page-subtitle">Pricing Intelligence Übersicht</p>
            </div>
            {pendingCount > 0 && (
              <div className="vlerafy-alert-inline">
                <span className="vlerafy-alert-dot" />
                <span>{pendingCount} Preisempfehlungen ausstehend</span>
                <Link href={`/dashboard/pricing${suffix}`} className="vlerafy-alert-link">
                  Jetzt ansehen →
                </Link>
              </div>
            )}
          </s-stack>
        </div>

        <s-grid columns="4" gap="4" className="vlerafy-dashboard-kpi-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 28 }}>
          <div className="vlerafy-kpi-card">
            <div className="vlerafy-kpi-card--accent-neutral" />
            <div className="vlerafy-kpi-body">
              <p className="vlerafy-kpi-label">Produkte synchronisiert</p>
              <p className="vlerafy-kpi-value">
                <AnimatedNumber value={syncedProducts} />
              </p>
            </div>
          </div>

          <div className="vlerafy-kpi-card">
            <div className="vlerafy-kpi-card--accent-warning" />
            <div className="vlerafy-kpi-body">
              <p className="vlerafy-kpi-label">Offene Empfehlungen</p>
              <p className="vlerafy-kpi-value">
                <AnimatedNumber value={pendingCount} />
              </p>
            </div>
          </div>

          <div className="vlerafy-kpi-card">
            <div className="vlerafy-kpi-card--accent-success" />
            <div className="vlerafy-kpi-body">
              <p className="vlerafy-kpi-label">Möglicher Mehrumsatz</p>
              <p className="vlerafy-kpi-value vlerafy-kpi-value--success">{revenue}</p>
            </div>
          </div>

          <div className="vlerafy-kpi-card">
            <div className="vlerafy-kpi-card--accent-neutral" />
            <div className="vlerafy-kpi-body">
              <p className="vlerafy-kpi-label">Empfehlungen umgesetzt</p>
              <p className="vlerafy-kpi-value">
                <AnimatedNumber value={appliedCount} />
              </p>
            </div>
          </div>
        </s-grid>

        <s-grid columns="2" gap="4" className="vlerafy-dashboard-bottom-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16, alignItems: 'start' }}>
          <FortschrittsCard progress={stats.progress} />

          <div className="vlerafy-quick-actions-card">
            <p className="vlerafy-quick-actions-title">Schnellaktionen</p>
            <div className="vlerafy-quick-actions-grid">
              <Link href={`/dashboard/pricing${suffix}`} className="vlerafy-quick-action-item">
                <span className="vlerafy-quick-action-icon">⚡</span>
                <span>Preise optimieren</span>
              </Link>
              <Link href={`/dashboard/products${suffix}`} className="vlerafy-quick-action-item">
                <span className="vlerafy-quick-action-icon">📦</span>
                <span>Produkte sync</span>
              </Link>
              <Link href={`/dashboard/analytics${suffix}`} className="vlerafy-quick-action-item">
                <span className="vlerafy-quick-action-icon">📈</span>
                <span>Analysen</span>
              </Link>
              <Link href={`/dashboard/settings${suffix}`} className="vlerafy-quick-action-item">
                <span className="vlerafy-quick-action-icon">⚙️</span>
                <span>Einstellungen</span>
              </Link>
            </div>
          </div>
        </s-grid>
      </s-stack>
    </div>
  );
}
