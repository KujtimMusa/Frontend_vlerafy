'use client';

import { useQuery } from '@tanstack/react-query';
import { getDashboardStats, getEngineStatus } from '@/lib/api';

export default function AnalyticsPage() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });
  const { data: engineStatus } = useQuery({
    queryKey: ['engine-status'],
    queryFn: getEngineStatus,
  });

  if (isLoading) return <s-skeleton-page />;

  return (
    <s-page title="Analysen">
      <s-card title="Ungenutztes Potenzial">
        <s-text variant="headingXl" tone="critical">
          €{stats?.missed_revenue?.total?.toFixed(2) ?? '0.00'}
        </s-text>
        <s-layout variant="1-1-1">
          <div>
            <s-text variant="headingLg">
              {stats?.missed_revenue?.product_count ?? 0}
            </s-text>
            <s-text>Betroffene Produkte</s-text>
          </div>
          <div>
            <s-text variant="headingLg">
              €
              {stats?.missed_revenue?.avg_per_product?.toFixed(2) ?? '0.00'}
            </s-text>
            <s-text>Ø pro Produkt</s-text>
          </div>
          <div>
            <s-text variant="headingLg">
              {stats?.missed_revenue?.recommendation_count ?? 0}
            </s-text>
            <s-text>Ausstehende Empfehlungen</s-text>
          </div>
        </s-layout>
        <s-button href="/dashboard/products">
          Produkte optimieren →
        </s-button>
      </s-card>

      <s-card title="Empfehlungs-Übersicht">
        <s-layout variant="1-1-1">
          <div>
            <s-text variant="headingLg">
              {stats?.recommendations_pending ?? 0}
            </s-text>
            <s-text>Ausstehend</s-text>
          </div>
          <div>
            <s-text variant="headingLg" tone="success">
              {stats?.recommendations_applied ?? 0}
            </s-text>
            <s-text>Angewendet</s-text>
          </div>
          <div>
            <s-text variant="headingLg">
              {stats?.products_with_recommendations ?? 0}
            </s-text>
            <s-text>Produkte mit Empfehlung</s-text>
          </div>
        </s-layout>
      </s-card>

      {engineStatus && (
        <s-card title="ML Pricing Engine">
          <s-badge
            tone={
              engineStatus.feature_flags ? 'success' : 'warning'
            }
          >
            {engineStatus.feature_flags ? 'Aktiv' : 'Prüfen'}
          </s-badge>
          <s-text>
            Engine: XGBoost v1.2 + Meta-Labeler
          </s-text>
        </s-card>
      )}

      <s-card title="Optimierungs-Fortschritt">
        <s-badge
          tone={
            stats?.progress.level === 'platinum'
              ? 'success'
              : stats?.progress.level === 'gold'
                ? 'warning'
                : stats?.progress.level === 'silver'
                  ? 'info'
                  : 'new'
          }
        >
          {stats?.progress.level?.toUpperCase() ?? 'BRONZE'}
        </s-badge>
        <s-progress-bar
          value={stats?.progress.points ?? 0}
          max={stats?.progress.next_level_points ?? 100}
        />
        <s-text>
          {stats?.progress.points_needed ?? 0} Punkte bis nächstes Level
        </s-text>
        {stats?.progress.pending_steps?.map((step) => (
          <s-list-item key={step.text}>
            {step.text} <s-badge>+{step.points} Punkte</s-badge>
          </s-list-item>
        ))}
      </s-card>
    </s-page>
  );
}
