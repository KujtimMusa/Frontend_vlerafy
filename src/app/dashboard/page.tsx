'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams, useRouter } from 'next/navigation';
import { getDashboardStats, getCurrentShop, syncProductsFromShopify } from '@/lib/api';
import { Page, Banner, Text, Button } from '@shopify/polaris';
import { RefreshIcon } from '@shopify/polaris-icons';

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

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('de-DE', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(value);
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
      <Page title="Dashboard">
        <div style={{ padding: 24, background: '#fff', borderRadius: 12 }}>
          Lade Dashboard...
        </div>
      </Page>
    );
  }

  if (error || !stats) {
    return (
      <Page title="Dashboard">
        <Banner tone="critical" title="Fehler beim Laden">
          Dashboard konnte nicht geladen werden.
          {error instanceof Error && ` (${error.message})`}
        </Banner>
      </Page>
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
      icon: '📦',
      color: '#6366F1',
      bg: '#EEF2FF',
      suffix: '',
      prefix: '',
    },
    {
      label: 'Offene Empfehlungen',
      value: openRecommendations,
      icon: '💡',
      color: '#F59E0B',
      bg: '#FFFBEB',
      suffix: '',
      prefix: '',
    },
    {
      label: 'Ungenutztes Potenzial',
      value: Math.abs(potentialRevenue),
      icon: '📈',
      color: '#10B981',
      bg: '#F0FDF4',
      prefix: '€',
      suffix: '',
      isNegative: potentialRevenue < 0,
    },
    {
      label: 'Empfehlungen umgesetzt',
      value: appliedRecommendations,
      icon: '✅',
      color: '#6366F1',
      bg: '#EEF2FF',
      suffix: '',
      prefix: '',
    },
  ];

  return (
    <Page title="Dashboard">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {/* A: Header */}
        <div style={{ marginBottom: 32 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 16,
            }}
          >
            <div>
              <Text variant="heading2xl" as="h1">
                Guten Tag, {shopName}! 👋
              </Text>
              <Text as="p" variant="bodyMd" tone="subdued">
                {new Date().toLocaleDateString('de-DE', {
                  weekday: 'long',
                  day: 'numeric',
                  month: 'long',
                  year: 'numeric',
                })}
              </Text>
            </div>
            <Button
              variant="primary"
              icon={RefreshIcon}
              onClick={handleSync}
              loading={isSyncing}
            >
              Synchronisieren
            </Button>
          </div>
        </div>

        {/* B: Alert Banner */}
        {openRecommendations > 0 && (
          <div
            style={{
              background: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)',
              borderRadius: 16,
              padding: '20px 24px',
              marginBottom: 24,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 16,
              boxShadow: '0 4px 24px rgba(99, 102, 241, 0.25)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 12,
                  background: 'rgba(255,255,255,0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <span style={{ fontSize: 24 }}>⚡</span>
              </div>
              <div>
                <p
                  style={{
                    color: 'white',
                    fontWeight: 700,
                    fontSize: 16,
                    margin: 0,
                    lineHeight: 1.4,
                  }}
                >
                  {openRecommendations} Preisempfehlungen warten auf dich
                </p>
                <p
                  style={{
                    color: 'rgba(255,255,255,0.8)',
                    fontSize: 14,
                    margin: 0,
                  }}
                >
                  Ungenutztes Potenzial: bis zu {formatCurrency(potentialRevenue)} mehr Umsatz
                </p>
              </div>
            </div>
            <button
              onClick={() => router.push(`/dashboard/pricing${suffix}`)}
              style={{
                background: 'white',
                color: '#6366F1',
                border: 'none',
                borderRadius: 10,
                padding: '10px 20px',
                fontWeight: 700,
                fontSize: 14,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
              }}
            >
              Jetzt optimieren →
            </button>
          </div>
        )}

        {/* C: Stats Cards */}
        <div
          className="dashboard-stats"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: 16,
            marginBottom: 24,
          }}
        >
          {statsData.map((stat) => (
            <div
              key={stat.label}
              style={{
                background: 'white',
                borderRadius: 16,
                padding: '20px 24px',
                border: '1px solid #E2E8F0',
                boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
                transition: 'box-shadow 0.2s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.08)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.04)';
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 12,
                }}
              >
                <span style={{ fontSize: 13, color: '#64748B', fontWeight: 500 }}>
                  {stat.label}
                </span>
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 10,
                    background: stat.bg,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 18,
                  }}
                >
                  {stat.icon}
                </div>
              </div>
              <div
                style={{
                  fontSize: 32,
                  fontWeight: 800,
                  color: '#0F172A',
                  lineHeight: 1,
                }}
              >
                {stat.prefix || ''}
                {typeof stat.value === 'number'
                  ? stat.value.toLocaleString('de-DE')
                  : stat.value}
                {stat.suffix || ''}
              </div>
            </div>
          ))}
        </div>

        {/* D: Zwei-Spalten Layout */}
        <style>{`
          @media (max-width: 900px) {
            .dashboard-two-col { grid-template-columns: 1fr !important; }
          }
        `}</style>
        <div
          className="dashboard-two-col"
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 340px',
            gap: 20,
            alignItems: 'start',
          }}
        >
          {/* Linke Spalte: Fortschritt */}
          <div
            style={{
              background: 'white',
              borderRadius: 16,
              padding: '24px',
              border: '1px solid #E2E8F0',
              boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                marginBottom: 20,
              }}
            >
              <Text variant="headingMd" as="h2">
                Dein Fortschritt
              </Text>
              <span
                style={{
                  background:
                    level === 'BRONZE'
                      ? 'linear-gradient(135deg, #F59E0B, #D97706)'
                      : level === 'SILVER'
                        ? 'linear-gradient(135deg, #94A3B8, #64748B)'
                        : level === 'GOLD'
                          ? 'linear-gradient(135deg, #FBBF24, #F59E0B)'
                          : 'linear-gradient(135deg, #6366F1, #8B5CF6)',
                  color: 'white',
                  borderRadius: 20,
                  padding: '2px 12px',
                  fontSize: 12,
                  fontWeight: 700,
                }}
              >
                🏅 {level}
              </span>
            </div>

            {/* Progress Bar */}
            <div style={{ marginBottom: 8 }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginBottom: 8,
                }}
              >
                <span style={{ fontSize: 13, color: '#64748B' }}>
                  {pointsToNextLevel} Punkte bis {nextLevel}
                </span>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#6366F1' }}>
                  {currentPoints} / {maxPoints} Pkt.
                </span>
              </div>
              <div
                style={{
                  height: 10,
                  background: '#E2E8F0',
                  borderRadius: 99,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${progressPercent}%`,
                    background: 'linear-gradient(90deg, #6366F1, #8B5CF6)',
                    borderRadius: 99,
                    transition: 'width 0.6s ease',
                  }}
                />
              </div>
            </div>

            {/* Todo Liste */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
                marginTop: 20,
              }}
            >
              {todos.map((todo) => (
                <div
                  key={todo.label}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 16px',
                    background: todo.done ? '#F0FDF4' : '#F8FAFC',
                    borderRadius: 10,
                    border: `1px solid ${todo.done ? '#BBF7D0' : '#E2E8F0'}`,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 18 }}>
                      {todo.done ? '✅' : '⭕'}
                    </span>
                    <span
                      style={{
                        fontSize: 14,
                        color: todo.done ? '#64748B' : '#0F172A',
                        textDecoration: todo.done ? 'line-through' : 'none',
                      }}
                    >
                      {todo.label}
                    </span>
                  </div>
                  {!todo.done && (
                    <span
                      style={{
                        background: '#EEF2FF',
                        color: '#6366F1',
                        borderRadius: 20,
                        padding: '2px 10px',
                        fontSize: 12,
                        fontWeight: 700,
                      }}
                    >
                      +{todo.points} Pkt.
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Rechte Spalte: Schnellaktionen */}
          <div
            style={{
              background: 'white',
              borderRadius: 16,
              padding: '24px',
              border: '1px solid #E2E8F0',
              boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            }}
          >
            <Text variant="headingMd" as="h2">
              Schnellaktionen
            </Text>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
                marginTop: 16,
              }}
            >
              <button
                onClick={() => router.push(`/dashboard/pricing${suffix}`)}
                style={{
                  background: 'linear-gradient(135deg, #6366F1, #8B5CF6)',
                  color: 'white',
                  border: 'none',
                  borderRadius: 12,
                  padding: '14px 20px',
                  fontWeight: 700,
                  fontSize: 14,
                  cursor: 'pointer',
                  textAlign: 'left',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  boxShadow: '0 2px 12px rgba(99,102,241,0.3)',
                }}
              >
                <span>⚡</span>
                {openRecommendations} Preise optimieren
              </button>

              {[
                {
                  icon: '🔄',
                  label: 'Produkte synchronisieren',
                  onClick: handleSync,
                },
                {
                  icon: '📊',
                  label: 'Analysen anzeigen',
                  onClick: () => router.push(`/dashboard/analytics${suffix}`),
                },
                {
                  icon: '⚙️',
                  label: 'Einstellungen',
                  onClick: () => router.push(`/dashboard/settings${suffix}`),
                },
              ].map((action) => (
                <button
                  key={action.label}
                  onClick={action.onClick}
                  disabled={action.label === 'Produkte synchronisieren' && isSyncing}
                  style={{
                    background: '#F8FAFC',
                    color: '#0F172A',
                    border: '1px solid #E2E8F0',
                    borderRadius: 12,
                    padding: '12px 16px',
                    fontWeight: 500,
                    fontSize: 14,
                    cursor: 'pointer',
                    textAlign: 'left',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) => {
                    if (!e.currentTarget.disabled) {
                      e.currentTarget.style.background = '#EEF2FF';
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = '#F8FAFC';
                  }}
                >
                  <span>{action.icon}</span>
                  {action.label === 'Produkte synchronisieren' && isSyncing
                    ? 'Synchronisiere...'
                    : action.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </Page>
  );
}
