'use client';

import type { DashboardStats } from '@/types/models';

interface FortschrittsCardProps {
  progress: DashboardStats['progress'];
}

const LEVEL_EMOJI: Record<string, string> = {
  bronze: '🥉',
  silver: '🥈',
  gold: '🥇',
  platinum: '🏆',
};

const LEVEL_TONE: Record<string, 'attention' | 'info' | 'warning' | 'success'> = {
  bronze: 'attention',
  silver: 'info',
  gold: 'warning',
  platinum: 'success',
};

export function FortschrittsCard({ progress }: FortschrittsCardProps) {
  const nextLevel =
    progress.level === 'bronze'
      ? 'Silber'
      : progress.level === 'silver'
        ? 'Gold'
        : progress.level === 'gold'
          ? 'Platin'
          : 'Max';
  const emoji = LEVEL_EMOJI[progress.level] ?? '🥉';
  const tone = LEVEL_TONE[progress.level] ?? 'attention';
  const progressPercent =
    progress.next_level_points > 0
      ? (progress.points / progress.next_level_points) * 100
      : 0;

  return (
    <div className="vlerafy-quick-actions-card">
      <s-stack direction="block" gap="4">
        <s-heading size="md">Dein Fortschritt</s-heading>
        <s-badge tone={tone}>
          {`${emoji} ${progress.level.toUpperCase()}`}
        </s-badge>
        <div className="vlerafy-progress">
          <div
            className="vlerafy-progress-bar"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <s-paragraph tone="subdued">
          {progress.points_needed} Punkte bis {nextLevel}
        </s-paragraph>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {(progress.completed_steps ?? []).map((step) => (
            <div
              key={step}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '6px 0',
                borderBottom: '1px solid var(--v-gray-100)',
              }}
            >
              <div
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: '50%',
                  background: 'var(--v-success)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <span style={{ color: 'var(--v-white)', fontSize: 11 }}>✓</span>
              </div>
              <span
                style={{
                  fontSize: 13,
                  color: 'var(--v-gray-400)',
                  textDecoration: 'line-through',
                  flex: 1,
                }}
              >
                {String(step).replace(/^✅\s*/, '')}
              </span>
            </div>
          ))}
          {(progress.pending_steps ?? []).map((step) => (
            <div
              key={step.text}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '6px 0',
                borderBottom: '1px solid var(--v-gray-100)',
              }}
            >
              <div
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: '50%',
                  background: 'var(--v-gray-200)',
                  flexShrink: 0,
                }}
              />
              <span style={{ fontSize: 13, color: 'var(--v-gray-700)', flex: 1 }}>
                {step.text}
              </span>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--v-navy-700)',
                  background: 'var(--v-navy-50)',
                  padding: '2px 8px',
                  borderRadius: 'var(--v-radius-full)',
                }}
              >
                +{step.points} Pkt.
              </span>
            </div>
          ))}
        </div>
      </s-stack>
    </div>
  );
}
