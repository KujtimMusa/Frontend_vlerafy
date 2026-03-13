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
  const toneBackground: Record<typeof tone, string> = {
    neutral: '#F1F5F9',
    warning: '#FFFBEB',
    critical: '#FEF2F2',
    success: '#F0FDF4',
  };

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
              width: 32,
              height: 32,
              borderRadius: 8,
              background: toneBackground[tone],
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
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
