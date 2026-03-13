'use client';

import { Card, BlockStack, Text, InlineStack } from '@shopify/polaris';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface DataPoint {
  date: string;
  price: number;
}

interface PreisverlaufChartProps {
  data: DataPoint[];
  title?: string;
  subtitle?: string;
}

export function PreisverlaufChart({
  data,
  title = 'Preisentwicklung',
  subtitle = 'Letzte 30 Tage',
}: PreisverlaufChartProps) {
  return (
    <Card>
      <BlockStack gap="300">
        <InlineStack align="space-between">
          <Text as="h3" variant="headingMd">{title}</Text>
          <Text as="span" tone="subdued" variant="bodySm">
            {subtitle}
          </Text>
        </InlineStack>
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart
              data={data}
              margin={{ top: 5, right: 10, bottom: 5, left: 0 }}
            >
              <defs>
                <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#4F46E5" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#4F46E5" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={(v: number) => `${v}€`}
              />
              <Tooltip
                formatter={(v) => [
                  `${Number(v ?? 0).toFixed(2)}€`,
                  'Preis',
                ]}
                contentStyle={{
                  borderRadius: 8,
                  border: '1px solid #e5e7eb',
                }}
              />
              <Area
                type="monotone"
                dataKey="price"
                stroke="#4F46E5"
                strokeWidth={2}
                fill="url(#priceGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <Text as="p" tone="subdued">
            Noch keine Preishistorie vorhanden. Preisänderungen werden hier
            angezeigt.
          </Text>
        )}
      </BlockStack>
    </Card>
  );
}
