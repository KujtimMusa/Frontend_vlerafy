'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import { getDashboardStats } from '@/lib/api';

type Period = 'Tag' | 'Monat' | 'Jahr';

const TIER_LABELS: Record<string, string> = {
  bronze: 'BRONZE', silver: 'SILBER', gold: 'GOLD', platinum: 'PLATIN',
};
const TIER_EMOJI: Record<string, string> = {
  bronze: '⭐', silver: '🥈', gold: '🥇', platinum: '💎',
};
const NEXT_LABELS: Record<string, string> = {
  bronze: 'Silber', silver: 'Gold', gold: 'Platin', platinum: 'Max',
};

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

export default function DashboardPage() {
  const router  = useRouter();
  const suffix  = useShopSuffix();
  const [activePeriod,  setActivePeriod ] = useState<Period>('Monat');
  const [noticeVisible, setNoticeVisible] = useState(true);

  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn:  getDashboardStats,
  });

  /* ── Daten-Derivate ── */
  const totalRevenuePotential = stats?.missed_revenue?.total ?? 0;
  const pendingCount          = stats?.recommendations_pending ?? 0;
  const avgPerProduct         = stats?.missed_revenue?.avg_per_product ?? 0;
  const nextStepsCount        = stats?.next_steps?.length ?? 0;

  /* ── Gamification ── */
  const level           = stats?.progress?.level ?? 'bronze';
  const points          = stats?.progress?.points ?? 0;
  const nextLevelPoints = stats?.progress?.next_level_points ?? 20;
  const pointsNeeded    = stats?.progress?.points_needed ?? 20;
  const completedSteps  = stats?.progress?.completed_steps ?? [];
  const pendingSteps    = stats?.progress?.pending_steps ?? [];
  const tierPercent     = nextLevelPoints > 0
    ? Math.min(Math.round((points / nextLevelPoints) * 100), 100)
    : 0;
  const nextLevelLabel = NEXT_LABELS[level] ?? 'Silber';

  /* ── Period-Umsatz ── */
  const getRevenue = (period: Period): number => {
    switch (period) {
      case 'Tag':   return Math.round(totalRevenuePotential / 30);
      case 'Monat': return totalRevenuePotential;
      case 'Jahr':  return totalRevenuePotential * 12;
    }
  };

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
        <s-banner tone="critical" title="Fehler beim Laden">
          <s-paragraph>
            Dashboard konnte nicht geladen werden.
            {error instanceof Error && ` (${error.message})`}
          </s-paragraph>
        </s-banner>
      </s-page>
    );
  }

  return (
    <s-page title="Übersicht">
      <div className="piq-dashboard">

        {/* ── Notification Banner (kein s-banner, da dismissible ohne s-* Violations) ── */}
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
              <s-button
                variant="primary"
                size="slim"
                onClick={() => router.push(`/dashboard/pricing${suffix}`)}
              >
                Empfehlungen ansehen
              </s-button>
              <button
                className="piq-notice-dismiss"
                onClick={() => setNoticeVisible(false)}
                aria-label="Benachrichtigung schließen"
              >
                ×
              </button>
            </div>
          </div>
        )}

        {/* ══ ZEILE 1: 3 KPI-Cards via s-grid + s-section ══ */}
        <s-grid columns="3" gap="base" className="kpi-grid">

          {/* Card 1: Entgangener Umsatz mit Period-Tabs */}
          <s-section>
            <span slot="heading">Entgangener Umsatz</span>
            <div className="kpi-card-inner">
              <div className="period-tabs">
                {(['Tag', 'Monat', 'Jahr'] as const).map((p) => (
                  <button
                    key={p}
                    className={`period-tab${activePeriod === p ? ' period-tab--active' : ''}`}
                    onClick={() => setActivePeriod(p)}
                  >
                    {p}
                  </button>
                ))}
              </div>
              <s-text variant="heading2xl" font-weight="bold">
                +€{getRevenue(activePeriod).toLocaleString('de-DE')}
              </s-text>
              <s-text tone="subdued" variant="bodySm">
                bei Umsetzung aller Empfehlungen
              </s-text>
              <s-badge tone="success">Potenzial</s-badge>
            </div>
          </s-section>

          {/* Card 2: Ausstehende Empfehlungen */}
          <s-section>
            <span slot="heading">Ausstehende Empfehlungen</span>
            <div className="kpi-card-inner">
              <s-text variant="heading2xl" font-weight="bold" tone="caution">
                {pendingCount}
              </s-text>
              <s-text tone="subdued" variant="bodySm">
                offene Preisempfehlungen
              </s-text>
              {pendingCount > 0
                ? <s-badge tone="warning">Handlung erforderlich</s-badge>
                : <s-badge tone="success">Alles erledigt</s-badge>
              }
            </div>
          </s-section>

          {/* Card 3: Ø Mehrumsatz pro Produkt (dritte verfügbare KPI) */}
          <s-section>
            <span slot="heading">Ø pro Produkt</span>
            <div className="kpi-card-inner">
              <s-text variant="heading2xl" font-weight="bold">
                €{Math.abs(Math.round(avgPerProduct)).toLocaleString('de-DE')}
              </s-text>
              <s-text tone="subdued" variant="bodySm">
                möglicher Mehrumsatz je Produkt
              </s-text>
              <s-badge tone="info">Produktdurchschnitt</s-badge>
            </div>
          </s-section>

        </s-grid>

        {/* ══ ZEILE 2: Nächste Schritte – 2 Step-Cards nebeneinander ══ */}
        {nextStepsCount > 0 && (
          <s-section>
            <s-stack direction="row" gap="200" block-align="center" slot="heading">
              <span>Nächste Schritte</span>
              <s-badge
                tone={stats.next_steps!.some((s) => s.urgent) ? 'critical' : 'attention'}
              >
                {nextStepsCount} ausstehend
              </s-badge>
            </s-stack>

            <s-grid columns="2" gap="base">
              {stats.next_steps!.slice(0, 2).map((step, i) => (
                <div key={i} className="step-card">
                  <s-stack direction="row" gap="300" block-align="start">
                    <s-box
                      background={step.urgent ? 'bg-surface-critical' : 'bg-surface-warning'}
                      border-radius="100"
                      padding="150"
                    >
                      <span aria-hidden="true">{step.urgent ? '🔥' : '📊'}</span>
                    </s-box>
                    <s-stack direction="column" gap="100">
                      <s-text font-weight="semibold">{step.title}</s-text>
                      <s-text tone="subdued" variant="bodySm">{step.description}</s-text>
                    </s-stack>
                  </s-stack>
                  <div className="step-card-divider" />
                  <s-button
                    variant={step.urgent ? 'primary' : 'secondary'}
                    onClick={() => router.push(`${step.href}${suffix}`)}
                  >
                    {step.urgent ? '⚡ Jetzt umsetzen' : '📊 Öffnen'}
                  </s-button>
                </div>
              ))}
            </s-grid>
          </s-section>
        )}

        {/* ══ ZEILE 3: native CSS Grid – Fortschritt (2fr) + Schnellaktionen (1fr) ══
            Kein s-grid: align-items: stretch ist in s-grid nicht zuverlässig
        */}
        <div className="bottom-grid">

          {/* Fortschritt: 2/3 Breite */}
          <s-section>
            <s-stack direction="row" gap="300" block-align="center" slot="heading">
              <span>Fortschritt</span>
              <span className="tier-badge">
                {TIER_EMOJI[level] ?? '⭐'} {TIER_LABELS[level] ?? 'BRONZE'}
              </span>
              <s-text tone="subdued" variant="bodySm">
                {points} / {nextLevelPoints}
              </s-text>
            </s-stack>

            <s-stack direction="column" gap="400">
              <s-stack direction="column" gap="150">
                <s-progress-indicator progress={tierPercent.toString()} />
                <s-text tone="subdued" variant="bodySm">
                  {pointsNeeded} Punkte bis {nextLevelLabel}
                </s-text>
              </s-stack>

              {/* Milestone-Liste */}
              <s-stack direction="column" gap="200">
                {(completedSteps ?? []).map((step, i) => (
                  <div key={`done-${i}`} className="piq-task">
                    <div className="piq-task-circle piq-task-circle--done">
                      <div className="piq-task-check" />
                    </div>
                    <span className="piq-task-label piq-task-label--done">
                      {String(step).replace(/^✅\s*/, '')}
                    </span>
                  </div>
                ))}
                {(pendingSteps ?? []).map((step, i) => (
                  <div key={`pending-${i}`} className="piq-task">
                    <div className="piq-task-circle" />
                    <span className="piq-task-label">{step.text}</span>
                    {step.points > 0 && (
                      <span className="piq-task-pts">+{step.points}</span>
                    )}
                  </div>
                ))}
              </s-stack>
            </s-stack>
          </s-section>

          {/* Schnellaktionen: 1/3 Breite, gleiche Höhe */}
          <s-section>
            <span slot="heading">Schnellaktionen</span>
            <div className="quickactions-inner">
              <s-button
                variant="secondary"
                onClick={() => router.push(`/dashboard/pricing${suffix}`)}
              >
                ⚡ Preise optimieren
              </s-button>
              <s-button
                variant="secondary"
                onClick={() => router.push(`/dashboard/products${suffix}`)}
              >
                📦 Produkte synchronisieren
              </s-button>
              <s-button
                variant="secondary"
                onClick={() => router.push(`/dashboard/settings${suffix}`)}
              >
                ⚙️ Einstellungen
              </s-button>
            </div>
          </s-section>

        </div>

      </div>

    </s-page>
  );
}
