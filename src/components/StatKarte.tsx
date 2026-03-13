'use client';

import { Card, BlockStack, Text } from '@shopify/polaris';
import type { ReactNode } from 'react';

export interface StatKarteProps {
  value: string | number;
  label: string;
  icon: ReactNode;
  tone?: 'neutral' | 'success' | 'warning' | 'critical';
  trend?: { value: number; label: string };
}

export function StatKarte({
  value,
  label,
  icon,
  tone = 'neutral',
  trend,
}: StatKarteProps) {
  const toneMap = {
    neutral: { bg: '#f3f4f6', color: '#374151' },
    success: { bg: '#ecfdf5', color: '#059669' },
    warning: { bg: '#fffbeb', color: '#d97706' },
    critical: { bg: '#fef2f2', color: '#dc2626' },
  };
  const t = toneMap[tone];

  return (
    <Card>
      <BlockStack gap="200">
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
          }}
        >
          <Text as="h2" variant="headingXl">
            {value}
          </Text>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 10,
              background: t.bg,
              color: t.color,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {icon}
          </div>
        </div>
        <Text as="p" tone="subdued" variant="bodySm">
          {label}
        </Text>
        {trend && (
          <Text as="p" variant="bodySm" tone="success">
            {trend.value > 0 ? '+' : ''}
            {trend.value}% {trend.label}
          </Text>
        )}
      </BlockStack>
    </Card>
  );
}
