'use client';

import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts';

interface ChartProduct {
  name: string;
  potential: number;
  confidence: number;
}

interface TopProductsChartProps {
  recommendations: Array<{
    product_name: string;
    recommended_price: number;
    current_price: number;
    confidence: number;
  }>;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  return (
    <div className="piq-chart-tip">
      <div className="piq-chart-tip-name">{d?.name}</div>
      <div className="piq-chart-tip-val">
        +€{payload[0]?.value?.toLocaleString('de-DE', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })}{' '}
        Potenzial
      </div>
      <div className="piq-chart-tip-conf">
        {Math.round((d?.confidence ?? 0) * 100)}% Konfidenz
      </div>
    </div>
  );
}

const truncate = (s: string, max = 22) =>
  s.length > max ? s.slice(0, max) + '…' : s;

const barColor = (c: number) => {
  if (c >= 0.8) return '#059669'; // green – hohe Konfidenz
  if (c >= 0.6) return '#4f46e5'; // indigo – mittlere Konfidenz
  return '#d97706';               // amber – niedrige Konfidenz
};

export function TopProductsChart({ recommendations }: TopProductsChartProps) {
  const data: ChartProduct[] = recommendations
    .filter((r) => r.recommended_price > r.current_price)
    .map((r) => ({
      name: truncate(r.product_name),
      potential: parseFloat((r.recommended_price - r.current_price).toFixed(2)),
      confidence: r.confidence,
    }))
    .sort((a, b) => b.potential - a.potential)
    .slice(0, 5);

  if (data.length === 0) {
    return (
      <div className="piq-chart-empty">
        <div className="piq-chart-empty-title">Noch keine Daten</div>
        <div className="piq-chart-empty-sub">
          Sobald Empfehlungen verfügbar sind, erscheint hier dein
          Potenzial-Ranking.
        </div>
      </div>
    );
  }

  return (
    <div className="piq-chart-wrap">
      <ResponsiveContainer width="100%" height={data.length * 44 + 24}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 56, left: 0, bottom: 4 }}
          barSize={22}
        >
          <CartesianGrid
            horizontal={false}
            strokeDasharray="3 3"
            stroke="var(--border)"
          />
          <XAxis
            type="number"
            tickFormatter={(v: number) => `€${v}`}
            tick={{ fontSize: 11, fill: 'var(--faint)', fontFamily: 'inherit' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={155}
            tick={{ fontSize: 12, fill: 'var(--ink)', fontFamily: 'inherit' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={{ fill: 'rgba(79,70,229,0.05)' }}
          />
          <Bar dataKey="potential" radius={[0, 5, 5, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={barColor(entry.confidence)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div className="piq-chart-legend">
        <span className="piq-chart-leg piq-chart-leg--green">
          ● Hohe Konfidenz (≥80%)
        </span>
        <span className="piq-chart-leg piq-chart-leg--indigo">
          ● Mittlere (60–79%)
        </span>
        <span className="piq-chart-leg piq-chart-leg--amber">
          ● Niedrige (&lt;60%)
        </span>
      </div>
    </div>
  );
}
