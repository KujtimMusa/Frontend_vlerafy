'use client';

import { useQuery } from '@tanstack/react-query';
import { getDashboardStats } from '@/lib/api';

export default function DashboardPage() {
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });

  if (isLoading) return <s-skeleton-page />;
  if (error || !stats)
    return (
      <s-banner tone="critical" title="Fehler beim Laden">
        Dashboard konnte nicht geladen werden.
      </s-banner>
    );

  const nextLevel =
    stats.progress.level === 'bronze'
      ? 'Silver'
      : stats.progress.level === 'silver'
        ? 'Gold'
        : stats.progress.level === 'gold'
          ? 'Platinum'
          : '🏆 Max';

  const urgentStep = stats.next_steps?.find((s) => s.urgent);

  return (
    <s-page title="Dashboard">
      {urgentStep && (
        <s-banner tone="warning" title={urgentStep.title}>
          {urgentStep.description}
          <s-button href={urgentStep.href}>{urgentStep.action}</s-button>
        </s-banner>
      )}

      <s-layout variant="1-1-1-1">
        <s-card>
          <s-text variant="headingLg">{stats.products_count}</s-text>
          <s-text>Produkte</s-text>
        </s-card>
        <s-card>
          <s-text variant="headingLg">{stats.recommendations_pending}</s-text>
          <s-text>Offene Empfehlungen</s-text>
        </s-card>
        <s-card>
          <s-text variant="headingLg" tone="critical">
            €{stats.missed_revenue.total.toFixed(2)}
          </s-text>
          <s-text>Ungenutztes Potenzial</s-text>
        </s-card>
        <s-card>
          <s-text variant="headingLg" tone="success">
            {stats.recommendations_applied}
          </s-text>
          <s-text>Empfehlungen angewendet</s-text>
        </s-card>
      </s-layout>

      <s-layout variant="1-1">
        <s-card title="Dein Fortschritt">
          <s-badge
            tone={
              stats.progress.level === 'platinum'
                ? 'success'
                : stats.progress.level === 'gold'
                  ? 'warning'
                  : stats.progress.level === 'silver'
                    ? 'info'
                    : 'new'
            }
          >
            {stats.progress.level.toUpperCase()}
          </s-badge>
          <s-progress-bar
            value={stats.progress.points}
            max={stats.progress.next_level_points}
          />
          <s-text>
            {stats.progress.points}/{stats.progress.next_level_points} Punkte
            bis {nextLevel}
          </s-text>
          {stats.progress.completed_steps.map((step) => (
            <s-list-item key={step}>✓ {step}</s-list-item>
          ))}
          {stats.progress.pending_steps.map((step) => (
            <s-list-item key={step.text}>
              ○ {step.text} <s-badge>+{step.points} Punkte</s-badge>
            </s-list-item>
          ))}
        </s-card>

        <s-card title="Nächste Schritte">
          {stats.next_steps?.map((step) => (
            <s-button key={step.title} href={step.href} variant="plain">
              {step.title} →
            </s-button>
          ))}
        </s-card>
      </s-layout>
    </s-page>
  );
}
