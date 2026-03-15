'use client';

import type { ReactNode } from 'react';

export interface StatKarteProps {
  value: string | number;
  label: string;
  icon: ReactNode;
  tone?: 'neutral' | 'success' | 'warning' | 'critical';
  trend?: { value: number; label: string };
}

const TONE_BG: Record<string, string> = {
  neutral: 'var(--v-gray-100)',
  warning: 'var(--v-warning-bg)',
  critical: 'var(--v-critical-bg)',
  success: 'var(--v-success-bg)',
};

export function StatKarte({
  value,
  label,
  icon,
  tone = 'neutral',
  trend,
}: StatKarteProps) {
  return (
    <div className="vlerafy-stat-card">
      <s-stack direction="block" gap="2">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <s-heading size="xl">{value}</s-heading>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: TONE_BG[tone],
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            {icon}
          </div>
        </div>
        <s-paragraph tone="subdued">{label}</s-paragraph>
        {trend && (
          <s-paragraph tone="success">
            {trend.value > 0 ? '+' : ''}
            {trend.value}% {trend.label}
          </s-paragraph>
        )}
      </s-stack>
    </div>
  );
}
