'use client';

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
    <s-section>
      <s-stack direction="block" gap="3">
        <s-stack direction="inline" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <s-heading size="md">{title}</s-heading>
          <s-paragraph tone="subdued">{subtitle}</s-paragraph>
        </s-stack>
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart
              data={data}
              margin={{ top: 5, right: 10, bottom: 5, left: 0 }}
            >
              <defs>
                <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--v-navy-700)" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="var(--v-navy-700)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--v-gray-200)" />
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
                  border: '1px solid var(--v-gray-200)',
                }}
              />
              <Area
                type="monotone"
                dataKey="price"
                stroke="var(--v-navy-700)"
                strokeWidth={2}
                fill="url(#priceGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <s-paragraph tone="subdued">
            Noch keine Preishistorie vorhanden. Preisänderungen werden hier
            angezeigt.
          </s-paragraph>
        )}
      </s-stack>
    </s-section>
  );
}
