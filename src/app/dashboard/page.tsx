'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams, useRouter } from 'next/navigation';
import { getDashboardStats, getCurrentShop, syncProductsFromShopify } from '@/lib/api';

function useShopSuffix(): string {
  const searchParams = useSearchParams();
  const shop = searchParams.get('shop') ?? (typeof window !== 'undefined' ? localStorage.getItem('shop_domain') : null) ?? '';
  const host = searchParams.get('host') ?? (typeof window !== 'undefined' ? localStorage.getItem('shopify_host') : null) ?? '';
  const shopId = searchParams.get('shop_id') ?? (typeof window !== 'undefined' ? localStorage.getItem('current_shop_id') : null) ?? '';
  const idToken = searchParams.get('id_token') ?? '';
  const p = new URLSearchParams();
  if (shop) p.set('shop', shop);
  if (host) p.set('host', host);
  if (shopId) p.set('shop_id', shopId);
  if (idToken) p.set('id_token', idToken);
  const q = p.toString();
  return q ? `?${q}` : '';
}

export default function DashboardPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const suffix = useShopSuffix();

  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });
  const { data: shopData } = useQuery({
    queryKey: ['current-shop'],
    queryFn: getCurrentShop,
  });
  const syncMutation = useMutation({
    mutationFn: syncProductsFromShopify,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });

  const shopName = shopData?.shop?.name ?? shopData?.shop?.shop_url ?? 'dein Shop';
  const openRecommendations = stats?.recommendations_pending ?? 0;
  const potentialRevenue = stats?.missed_revenue?.total ?? 0;
  const totalProducts = stats?.products_count ?? 0;
  const appliedRecommendations = stats?.recommendations_applied ?? 0;

  const handleSync = () => syncMutation.mutate();
  const isSyncing = syncMutation.isPending;

  if (isLoading) {
    return (
      <div className="vlerafy-main">
        <div style={{ padding: 24, background: 'var(--v-white)', borderRadius: 'var(--v-radius-md)' }}>
          Lade Dashboard...
        </div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="vlerafy-main">
        <s-banner tone="critical" title="Fehler beim Laden">
          Dashboard konnte nicht geladen werden.
          {error instanceof Error && ` (${error.message})`}
        </s-banner>
      </div>
    );
  }

  const progress = stats.progress;
  const level = progress.level.toUpperCase();
  const nextLevel =
    progress.level === 'bronze'
      ? 'Silber'
      : progress.level === 'silver'
        ? 'Gold'
        : progress.level === 'gold'
          ? 'Platin'
          : 'Max';
  const pointsToNextLevel = progress.points_needed;
  const currentPoints = progress.points;
  const maxPoints = progress.next_level_points;
  const progressPercent = maxPoints > 0 ? (currentPoints / maxPoints) * 100 : 0;

  const todos = [
    ...(progress.completed_steps ?? []).map((label) => ({ label: label.replace(/^✅\s*/, ''), done: true, points: 0 })),
    ...(progress.pending_steps ?? []).map((step) => ({ label: step.text, done: false, points: step.points })),
  ];

  const statsData = [
    {
      label: 'Produkte synchronisiert',
      value: totalProducts,
      icon: '◫',
      suffix: '',
      prefix: '',
      valueColor: 'var(--v-gray-950)',
    },
    {
      label: 'Offene Empfehlungen',
      value: openRecommendations,
      icon: '◈',
      suffix: '',
      prefix: '',
      valueColor: 'var(--v-gray-950)',
    },
    {
      label: 'Möglicher Mehrumsatz',
      value: Math.abs(potentialRevenue),
      icon: '▤',
      prefix: '+€',
      suffix: '',
      valueColor: 'var(--v-success)',
    },
    {
      label: 'Empfehlungen umgesetzt',
      value: appliedRecommendations,
      icon: '✅',
      suffix: '',
      prefix: '',
      valueColor: 'var(--v-gray-950)',
    },
  ];

  return (
    <div className="vlerafy-main">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        <div className="vlerafy-page-header" style={{ marginBottom: 28 }}>
          <s-stack direction="inline" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <h1 className="vlerafy-page-title">Guten Tag, {shopName}</h1>
              <p className="vlerafy-page-subtitle">
                {new Date().toLocaleDateString('de-DE', {
                  weekday: 'long',
                  day: 'numeric',
                  month: 'long',
                })}
              </p>
            </div>
            <s-button variant="secondary" onClick={handleSync} disabled={isSyncing} loading={isSyncing}>
              Synchronisieren
            </s-button>
          </s-stack>
        </div>

        {openRecommendations > 0 && (
          <div
            style={{
              background: 'var(--v-navy-900)',
              borderRadius: 'var(--v-radius-md)',
              padding: '16px 20px',
              marginBottom: 20,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 12,
              border: '1px solid var(--v-gray-900)',
            }}
          >
            <s-stack direction="inline" style={{ alignItems: 'center', gap: 14 }}>
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 'var(--v-radius-sm)',
                  background: 'var(--v-navy-800)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  fontSize: 16,
                }}
              >
                ⚡
              </div>
              <div>
                <p style={{ color: 'var(--v-gray-100)', fontWeight: 600, fontSize: 14, margin: 0 }}>
                  {openRecommendations} Preisempfehlungen ausstehend
                </p>
                <p style={{ color: 'var(--v-gray-500)', fontSize: 12, margin: '2px 0 0' }}>
                  Möglicher Mehrumsatz: +€
                  {Math.abs(potentialRevenue).toLocaleString('de-DE', { maximumFractionDigits: 0 })}
                </p>
              </div>
            </s-stack>
            <s-button variant="primary" onClick={() => router.push(`/dashboard/pricing${suffix}`)}>
              Jetzt ansehen →
            </s-button>
          </div>
        )}

        <div className="dashboard-stats" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, marginBottom: 24 }}>
          {statsData.map((stat) => (
            <div key={stat.label} className="vlerafy-stat-card">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <span className="vlerafy-stat-label">{stat.label}</span>
                <div style={{ width: 36, height: 36, borderRadius: 10, background: 'var(--v-gray-50)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, color: 'var(--v-gray-500)' }}>
                  {stat.icon}
                </div>
              </div>
              <p className="vlerafy-stat-value" style={{ color: stat.valueColor }}>
                {stat.prefix || ''}
                {typeof stat.value === 'number' ? stat.value.toLocaleString('de-DE') : stat.value}
                {stat.suffix || ''}
              </p>
            </div>
          ))}
        </div>

        <style>{`@media (max-width: 900px) { .dashboard-two-col { grid-template-columns: 1fr !important; } }`}</style>
        <div className="dashboard-two-col" style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 20, alignItems: 'start' }}>
          <s-section>
            <s-stack direction="block" gap="4">
              <s-stack direction="inline" style={{ alignItems: 'center', gap: 12, marginBottom: 8 }}>
                <s-heading size="md">Dein Fortschritt</s-heading>
                <span
                  style={{
                    background: level === 'BRONZE' ? 'var(--v-warning)' : level === 'SILVER' ? 'var(--v-gray-500)' : level === 'GOLD' ? 'var(--v-warning)' : 'var(--v-navy-800)',
                    color: 'var(--v-white)',
                    borderRadius: 'var(--v-radius-full)',
                    padding: '2px 12px',
                    fontSize: 12,
                    fontWeight: 700,
                  }}
                >
                  🏅 {level}
                </span>
              </s-stack>

              <div style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ fontSize: 13, color: 'var(--v-gray-500)' }}>
                    {pointsToNextLevel} Punkte bis {nextLevel}
                  </span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--v-navy-700)' }}>
                    {currentPoints} / {maxPoints} Pkt.
                  </span>
                </div>
                <div className="vlerafy-progress">
                  <div className="vlerafy-progress-bar" style={{ width: `${progressPercent}%` }} />
                </div>
              </div>

              <s-stack direction="block" gap="2" style={{ marginTop: 12 }}>
                {todos.map((todo) => (
                  <div
                    key={todo.label}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '12px 16px',
                      background: todo.done ? 'var(--v-success-bg)' : 'var(--v-gray-50)',
                      borderRadius: 'var(--v-radius-md)',
                      border: `1px solid ${todo.done ? 'var(--v-success-muted)' : 'var(--v-gray-200)'}`,
                    }}
                  >
                    <s-stack direction="inline" style={{ alignItems: 'center', gap: 10 }}>
                      <span style={{ fontSize: 18 }}>{todo.done ? '✅' : '⭕'}</span>
                      <span style={{ fontSize: 14, color: todo.done ? 'var(--v-gray-500)' : 'var(--v-gray-950)', textDecoration: todo.done ? 'line-through' : 'none' }}>
                        {todo.label}
                      </span>
                    </s-stack>
                    {!todo.done && (
                      <span style={{ background: 'var(--v-navy-50)', color: 'var(--v-navy-700)', borderRadius: 'var(--v-radius-full)', padding: '2px 10px', fontSize: 12, fontWeight: 700 }}>
                        +{todo.points} Pkt.
                      </span>
                    )}
                  </div>
                ))}
              </s-stack>
            </s-stack>
          </s-section>

          <s-section>
            <s-stack direction="block" gap="4">
              <s-heading size="md">Schnellaktionen</s-heading>
              <s-stack direction="block" gap="3">
                <s-button variant="primary" onClick={() => router.push(`/dashboard/pricing${suffix}`)} style={{ width: '100%', justifyContent: 'flex-start' }}>
                  ⚡ {openRecommendations} Preise optimieren
                </s-button>
                <s-button variant="secondary" onClick={handleSync} disabled={isSyncing} loading={isSyncing} style={{ width: '100%', justifyContent: 'flex-start' }}>
                  Produkte synchronisieren
                </s-button>
                <s-button variant="plain" onClick={() => router.push(`/dashboard/analytics${suffix}`)} style={{ width: '100%', justifyContent: 'flex-start' }}>
                  Analysen anzeigen
                </s-button>
                <s-button variant="plain" onClick={() => router.push(`/dashboard/settings${suffix}`)} style={{ width: '100%', justifyContent: 'flex-start' }}>
                  Einstellungen
                </s-button>
              </s-stack>
            </s-stack>
          </s-section>
        </div>
      </div>
    </div>
  );
}
