/*
 * Polaris Web konform: s-banner, s-button, s-section, s-stack, s-paragraph, s-heading.
 * KPI-Strip und Card-Layout bleiben Custom (Polaris hat kein Stats-Grid),
 * Inhalte nutzen Polaris-Komponenten.
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
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="var(--p-color-text-critical, #dc2626)" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="7" cy="7" r="5.5" />
      <path d="M7 4.5v3M7 9.5h.01" />
    </svg>
  );
}

function CostIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="var(--p-color-text-info, #2563eb)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="3" width="10" height="9" rx="1.5" />
      <path d="M2 6h10M5 3V1M9 3V1" />
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
      <s-page title="Übersicht">
        <div className="piq-dashboard">
        <s-section>
          <s-stack direction="block" gap="4">
            <s-paragraph tone="subdued">Lade Dashboard...</s-paragraph>
          </s-stack>
        </s-section>
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

  const affectedCount = stats?.missed_revenue?.product_count ?? 0;
  const totalCount = stats?.products_count ?? 1;
  const progressPct = totalCount > 0 ? Math.min((affectedCount / totalCount) * 100, 100) : 0;

  const nextStepsCount = stats?.next_steps?.length ?? 0;

  return (
    <s-page title="Übersicht">
    <div className="piq-dashboard">
      {/* Banner — Polaris s-banner */}
      {bannerVisible && pendingCount > 0 && (
        <s-banner
          tone="warning"
          title={`${pendingCount} Preisempfehlungen ausstehend`}
          onDismiss={() => setBannerVisible(false)}
        >
          <s-stack direction="block" gap="2">
            <s-paragraph>
              Durchschnittlich +€{avgPerProduct.toFixed(0)} Mehrumsatz pro Produkt möglich.
            </s-paragraph>
            <s-button variant="primary" size="slim" onClick={handleViewRecommendations}>
              Jetzt ansehen →
            </s-button>
          </s-stack>
        </s-banner>
      )}

      {/* KPI Strip — Custom Grid (Polaris hat kein Stats-Grid), s-section Wrapper */}
      <s-section>
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
      </s-section>

      {/* Lower Grid */}
      <div className={`piq-lower ${!nextStepsCount ? 'piq-lower--single' : ''}`}>
        {nextStepsCount > 0 && (
          <s-section>
            <s-stack direction="block" gap="4">
              <s-stack direction="inline" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                <s-heading size="md">Nächste Schritte</s-heading>
                <s-paragraph tone="subdued">{nextStepsCount} ausstehend</s-paragraph>
              </s-stack>
              {stats.next_steps!.slice(0, 4).map((step, i) => (
                <Link
                  key={i}
                  href={`${step.href}${suffix}`}
                  className="piq-step"
                  style={{ textDecoration: 'none', color: 'inherit' }}
                >
                  <s-stack direction="inline" gap="3" style={{ alignItems: 'flex-start', width: '100%' }}>
                    <div className="piq-step-ic">
                      {step.urgent ? <AlertIcon /> : <CostIcon />}
                    </div>
                    <s-stack direction="block" gap="0" style={{ flex: 1, minWidth: 0 }}>
                      <s-paragraph>
                        <strong>{step.title}</strong>
                      </s-paragraph>
                      <s-paragraph tone="subdued">{step.description}</s-paragraph>
                    </s-stack>
                    <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ flexShrink: 0, marginTop: 4 }}>
                      <path d="M4.5 2l4 4.5-4 4.5" />
                    </svg>
                  </s-stack>
                </Link>
              ))}
            </s-stack>
          </s-section>
        )}

        <s-section>
          <s-stack direction="block" gap="4">
            <FortschrittsCard
              level={stats?.progress?.level ?? 'bronze'}
              points={stats?.progress?.points ?? 0}
              nextLevelPoints={stats?.progress?.next_level_points ?? 20}
              pointsNeeded={stats?.progress?.points_needed ?? 20}
              completedSteps={stats?.progress?.completed_steps ?? []}
              pendingSteps={stats?.progress?.pending_steps ?? []}
            />
            <s-stack direction="block" gap="3">
              <s-heading size="md">Schnellaktionen</s-heading>
              <s-stack direction="block" gap="2">
                <s-button
                  variant="secondary"
                  size="slim"
                  onClick={() => router.push(`/dashboard/pricing${suffix}`)}
                  style={{ width: '100%', justifyContent: 'flex-start' }}
                >
                  Preise optimieren
                </s-button>
                <s-button
                  variant="secondary"
                  size="slim"
                  onClick={() => router.push(`/dashboard/products${suffix}`)}
                  style={{ width: '100%', justifyContent: 'flex-start' }}
                >
                  Produkte synchronisieren
                </s-button>
                <s-button
                  variant="secondary"
                  size="slim"
                  onClick={() => router.push(`/dashboard/settings${suffix}`)}
                  style={{ width: '100%', justifyContent: 'flex-start' }}
                >
                  Einstellungen
                </s-button>
              </s-stack>
            </s-stack>
          </s-stack>
        </s-section>
      </div>
    </div>
    </s-page>
  );
}

// ✅ BFS [Punkt 8] erledigt — s-page title="Übersicht" auf Dashboard
