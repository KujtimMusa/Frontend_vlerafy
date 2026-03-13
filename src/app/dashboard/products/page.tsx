'use client';

import { useEffect, useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  fetchProducts,
  getDashboardStats,
  getRecommendationsList,
  syncProductsFromShopify,
} from '@/lib/api';
import type { Product } from '@/types/models';

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
  return p.toString() ? `?${p.toString()}` : '';
}

export default function ProductsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const suffix = useShopSuffix();
  const autoSyncDone = useRef(false);
  const [searchQuery, setSearchQuery] = useState('');

  const { data: products = [], isLoading } = useQuery({
    queryKey: ['products'],
    queryFn: () => fetchProducts(),
  });
  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  });
  const { data: recsData } = useQuery({
    queryKey: ['recommendations-list'],
    queryFn: () => getRecommendationsList('all'),
  });
  const syncMutation = useMutation({
    mutationFn: syncProductsFromShopify,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      queryClient.invalidateQueries({ queryKey: ['recommendations-list'] });
    },
  });

  const productIdsWithRec = new Set((recsData?.recommendations ?? []).map((r) => r.product_id));
  const filteredProducts = (products ?? []).filter((p) =>
    p.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const totalProducts = stats?.products_count ?? products.length;
  const withRecommendation = stats?.products_with_recommendations ?? 0;
  const outOfStock = (products ?? []).filter((p) => (p.inventory ?? 0) === 0).length;
  const potentialRevenue = stats?.missed_revenue?.total ?? 0;
  const displayPotential = Math.abs(potentialRevenue);

  useEffect(() => {
    if (
      !isLoading &&
      products.length === 0 &&
      !autoSyncDone.current &&
      typeof window !== 'undefined' &&
      (localStorage.getItem('shop_domain') || localStorage.getItem('current_shop_id'))
    ) {
      autoSyncDone.current = true;
      syncMutation.mutate();
    }
  }, [isLoading, products.length, syncMutation]);

  const handleSync = () => syncMutation.mutate();
  const handleAnalyzeAll = () => router.push(`/dashboard/pricing${suffix}`);

  if (isLoading) {
    return (
      <div style={{ padding: 24 }}>
        <div style={{ height: 60, background: '#F1F5F9', borderRadius: 12, marginBottom: 20 }} />
        <div style={{ height: 200, background: '#F1F5F9', borderRadius: 12 }} />
      </div>
    );
  }

  if (products.length === 0 && !syncMutation.isPending) {
    return (
      <div style={{ padding: 24 }}>
        <div
          style={{
            background: 'white',
            borderRadius: 12,
            border: '1px solid #E2E8F0',
            padding: 48,
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: 48, marginBottom: 16 }}>📦</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#0F172A', marginBottom: 8 }}>
            Noch keine Produkte geladen
          </div>
          <div style={{ fontSize: 14, color: '#64748B', marginBottom: 20 }}>
            Verbinde deinen Shopify-Shop um smarte Preisempfehlungen zu erhalten.
          </div>
          <button
            onClick={handleSync}
            disabled={syncMutation.isPending}
            style={{
              background: '#1E3A5F',
              color: 'white',
              border: 'none',
              borderRadius: 8,
              padding: '10px 20px',
              fontSize: 14,
              fontWeight: 600,
              cursor: syncMutation.isPending ? 'wait' : 'pointer',
            }}
          >
            {syncMutation.isPending ? 'Synchronisiere...' : 'Produkte synchronisieren'}
          </button>
        </div>
      </div>
    );
  }

  const statsData = [
    {
      label: 'Produkte gesamt',
      value: String(totalProducts),
      valueColor: '#0F172A',
      icon: '◫',
      sub: null as string | null,
    },
    {
      label: 'Mit Empfehlung',
      value: String(withRecommendation),
      valueColor: '#1E3A5F',
      icon: '◈',
      sub: totalProducts > 0 ? `${Math.round((withRecommendation / totalProducts) * 100)}% aller Produkte` : null,
    },
    {
      label: 'Kein Lagerbestand',
      value: String(outOfStock),
      valueColor: outOfStock > 0 ? '#EF4444' : '#10B981',
      icon: '◎',
      sub: outOfStock > 0 ? 'Produkte prüfen' : 'Alles vorrätig',
    },
    {
      label: 'Möglicher Mehrumsatz',
      value: '+€' + displayPotential.toLocaleString('de-DE', { maximumFractionDigits: 0 }),
      valueColor: '#10B981',
      icon: '◉',
      sub: 'bei Umsetzung aller Empfehlungen',
    },
  ];

  return (
    <div style={{ padding: 24, background: '#F8FAFC', minHeight: '100vh' }}>
      {syncMutation.isPending && (
        <div
          style={{
            background: '#EFF6FF',
            border: '1px solid #BFDBFE',
            borderRadius: 8,
            padding: '12px 18px',
            marginBottom: 20,
            fontSize: 14,
            color: '#1E3A5F',
          }}
        >
          Produkte werden von deinem Shopify-Shop synchronisiert...
        </div>
      )}
      {syncMutation.isError && (
        <div
          style={{
            background: '#FEF2F2',
            border: '1px solid #FECACA',
            borderRadius: 8,
            padding: '12px 18px',
            marginBottom: 20,
            fontSize: 14,
            color: '#B91C1C',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <span>Sync fehlgeschlagen. Bitte erneut versuchen.</span>
          <button
            onClick={() => syncMutation.mutate()}
            style={{
              background: '#EF4444',
              color: 'white',
              border: 'none',
              borderRadius: 6,
              padding: '6px 12px',
              fontSize: 13,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Erneut versuchen
          </button>
        </div>
      )}

      <div style={{ marginBottom: 24 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <div>
            <h1
              style={{
                fontSize: 22,
                fontWeight: 700,
                color: '#0F172A',
                margin: 0,
              }}
            >
              Produkte
            </h1>
            <p style={{ fontSize: 13, color: '#94A3B8', margin: '3px 0 0' }}>
              {totalProducts} Produkte · {withRecommendation} mit Empfehlung
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={handleAnalyzeAll}
              style={{
                background: 'white',
                color: '#1E3A5F',
                border: '1px solid #BFDBFE',
                borderRadius: 8,
                padding: '7px 14px',
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Alle analysieren
            </button>
            <button
              onClick={handleSync}
              disabled={syncMutation.isPending}
              style={{
                background: '#0F172A',
                color: '#F1F5F9',
                border: '1px solid #1E293B',
                borderRadius: 8,
                padding: '7px 14px',
                fontSize: 13,
                fontWeight: 600,
                cursor: syncMutation.isPending ? 'wait' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              🔄 Synchronisieren
            </button>
          </div>
        </div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(195px, 1fr))',
          gap: 12,
          marginBottom: 20,
        }}
      >
        {statsData.map((stat) => (
          <div
            key={stat.label}
            style={{
              background: 'white',
              borderRadius: 12,
              padding: '16px 18px',
              border: '1px solid #E2E8F0',
              boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
              transition: 'box-shadow 0.15s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 3px 12px rgba(0,0,0,0.07)')}
            onMouseLeave={(e) => (e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.03)')}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                marginBottom: 8,
              }}
            >
              <span
                style={{
                  fontSize: 11,
                  color: '#94A3B8',
                  fontWeight: 500,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                }}
              >
                {stat.label}
              </span>
              <span style={{ fontSize: 16, color: '#CBD5E1' }}>{stat.icon}</span>
            </div>
            <div
              style={{
                fontSize: 26,
                fontWeight: 800,
                color: stat.valueColor,
                lineHeight: 1,
                marginBottom: stat.sub ? 6 : 0,
              }}
            >
              {stat.value}
            </div>
            {stat.sub && <div style={{ fontSize: 11, color: '#94A3B8' }}>{stat.sub}</div>}
          </div>
        ))}
      </div>

      <div
        style={{
          background: 'white',
          borderRadius: 12,
          border: '1px solid #E2E8F0',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: '12px 18px',
            borderBottom: '1px solid #F1F5F9',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <div style={{ position: 'relative' }}>
            <span
              style={{
                position: 'absolute',
                left: 9,
                top: '50%',
                transform: 'translateY(-50%)',
                color: '#94A3B8',
                fontSize: 13,
                pointerEvents: 'none',
              }}
            >
              🔍
            </span>
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Produkt suchen..."
              style={{
                paddingLeft: 28,
                paddingRight: 12,
                paddingTop: 6,
                paddingBottom: 6,
                border: '1px solid #E2E8F0',
                borderRadius: 7,
                fontSize: 13,
                outline: 'none',
                background: '#F8FAFC',
                color: '#0F172A',
                width: 220,
              }}
              onFocus={(e) => (e.target.style.borderColor = '#93C5FD')}
              onBlur={(e) => (e.target.style.borderColor = '#E2E8F0')}
            />
          </div>
          <span style={{ fontSize: 12, color: '#94A3B8' }}>{filteredProducts.length} Produkte</span>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 120px 100px 130px 90px',
            padding: '9px 18px',
            background: '#F8FAFC',
            borderBottom: '1px solid #F1F5F9',
          }}
        >
          {['Produkt', 'Preis', 'Lager', 'Empfehlung', ''].map((col) => (
            <span
              key={col}
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: '#94A3B8',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
              }}
            >
              {col}
            </span>
          ))}
        </div>

        {filteredProducts.map((product, i) => (
          <div
            key={product.id}
            onClick={() => router.push(`/dashboard/products/${product.id}${suffix}`)}
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 120px 100px 130px 90px',
              padding: '12px 18px',
              borderBottom: i < filteredProducts.length - 1 ? '1px solid #F8FAFC' : 'none',
              alignItems: 'center',
              cursor: 'pointer',
              transition: 'background 0.12s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = '#F8FAFC')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 7,
                  background: '#F1F5F9',
                  flexShrink: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 14,
                }}
              >
                📦
              </div>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 500,
                  color: '#0F172A',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {product.title}
              </span>
            </div>

            <span style={{ fontSize: 13, color: '#0F172A', fontWeight: 500 }}>
              {product.price?.toLocaleString('de-DE', { style: 'currency', currency: 'EUR' })}
            </span>

            <span
              style={{
                fontSize: 13,
                fontWeight: 600,
                color:
                  (product.inventory ?? 0) === 0
                    ? '#EF4444'
                    : (product.inventory ?? 0) < 10
                      ? '#F59E0B'
                      : '#64748B',
              }}
            >
              {(product.inventory ?? 0) === 0
                ? '⚠ 0 Stück'
                : `${product.inventory ?? 0} Stück`}
            </span>

            <div>
              {productIdsWithRec.has(product.id) ? (
                <span
                  style={{
                    background: '#EFF6FF',
                    color: '#1E3A5F',
                    border: '1px solid #BFDBFE',
                    borderRadius: 20,
                    padding: '2px 10px',
                    fontSize: 11,
                    fontWeight: 600,
                  }}
                >
                  ◈ Vorhanden
                </span>
              ) : (
                <span style={{ color: '#CBD5E1', fontSize: 13 }}>—</span>
              )}
            </div>

            <button
              onClick={(e) => {
                e.stopPropagation();
                router.push(`/dashboard/products/${product.id}${suffix}`);
              }}
              style={{
                background: 'transparent',
                color: '#1E3A5F',
                border: '1px solid #BFDBFE',
                borderRadius: 7,
                padding: '4px 12px',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.12s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#1E3A5F';
                e.currentTarget.style.color = 'white';
                e.currentTarget.style.borderColor = '#1E3A5F';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.color = '#1E3A5F';
                e.currentTarget.style.borderColor = '#BFDBFE';
              }}
            >
              Ansehen →
            </button>
          </div>
        ))}

        {filteredProducts.length === 0 && (
          <div style={{ padding: '40px 20px', textAlign: 'center' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>🔍</div>
            <div style={{ fontSize: 14, color: '#64748B' }}>
              Keine Produkte gefunden für „{searchQuery}"
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
