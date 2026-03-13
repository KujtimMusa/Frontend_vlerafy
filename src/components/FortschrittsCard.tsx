'use client';

import { Card, BlockStack, Text, Badge, ProgressBar } from '@shopify/polaris';
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

  return (
    <Card>
      <BlockStack gap="400">
        <Text as="h2" variant="headingMd">
          Dein Fortschritt
        </Text>
        <Badge tone={tone}>
          {`${emoji} ${progress.level.toUpperCase()}`}
        </Badge>
        <ProgressBar
          progress={
            progress.next_level_points > 0
              ? (progress.points / progress.next_level_points) * 100
              : 0
          }
          size="medium"
        />
        <Text as="p" tone="subdued">
          {progress.points_needed} Punkte bis {nextLevel}
        </Text>
        <div className="task-list">
          {(progress.completed_steps ?? []).map((step) => (
            <div key={step} className="task-item task-done">
              <div
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: '50%',
                  background: '#10B981',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <span style={{ color: 'white', fontSize: 11 }}>✓</span>
              </div>
              <span
                style={{
                  fontSize: 13,
                  color: '#9CA3AF',
                  textDecoration: 'line-through',
                  flex: 1,
                }}
              >
                {String(step).replace(/^✅\s*/, '')}
              </span>
            </div>
          ))}
          {(progress.pending_steps ?? []).map((step) => (
            <div key={step.text} className="task-item task-pending">
              <div
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: '50%',
                  background: '#E2E8F0',
                  flexShrink: 0,
                }}
              />
              <span style={{ fontSize: 13, color: '#374151', flex: 1 }}>
                {step.text}
              </span>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: '#6366F1',
                  background: '#EEF2FF',
                  padding: '2px 8px',
                  borderRadius: 99,
                }}
              >
                +{step.points} Pkt.
              </span>
            </div>
          ))}
        </div>
      </BlockStack>
    </Card>
  );
}
