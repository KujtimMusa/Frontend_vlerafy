'use client';

import {
  Card,
  BlockStack,
  Text,
  Badge,
  ProgressBar,
} from '@shopify/polaris';
import { CheckCircleIcon, BulletIcon } from '@shopify/polaris-icons';
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
              <CheckCircleIcon />
              <Text as="span" tone="subdued">
                <s>{String(step).replace(/^✅\s*/, '')}</s>
              </Text>
            </div>
          ))}
          {(progress.pending_steps ?? []).map((step) => (
            <div key={step.text} className="task-item task-pending">
              <BulletIcon />
              <Text as="span">
                {step.text}
              </Text>
              <Badge tone="info">{`+${step.points} Pkt.`}</Badge>
            </div>
          ))}
        </div>
      </BlockStack>
    </Card>
  );
}
