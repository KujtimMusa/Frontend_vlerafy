'use client';

import { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';

export function ShopVerbindungBanner() {
  const [show, setShow] = useState(false);
  const [domain, setDomain] = useState('');
  const [error, setError] = useState('');
  const queryClient = useQueryClient();

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const hasShop = localStorage.getItem('shop_domain') || localStorage.getItem('current_shop_id');
    setShow(!hasShop);
  }, []);

  const handleConnect = () => {
    const trimmed = domain.trim().toLowerCase();
    if (!trimmed) {
      setError('Bitte Shop-Domain eingeben');
      return;
    }
    const normalized = trimmed.includes('.myshopify.com')
      ? trimmed
      : `${trimmed}.myshopify.com`;
    if (!normalized.endsWith('.myshopify.com')) {
      setError('Format: dein-shop.myshopify.com');
      return;
    }
    setError('');
    localStorage.setItem('shop_domain', normalized);
    setShow(false);
    setDomain('');
    queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
    queryClient.invalidateQueries({ queryKey: ['products'] });
    queryClient.invalidateQueries({ queryKey: ['shops'] });
    // Kein window.location.reload() – TanStack Query-Invalidierung reicht für BFS-Compliance
  };

  if (!show) return null;

  return (
    <s-banner tone="warning" title="Shop nicht verbunden">
      <s-stack direction="block" gap="3">
        <s-paragraph>
          Kein Shop wurde erkannt. Öffne die App über den Shopify Admin, oder gib
          deine Shop-Domain ein:
        </s-paragraph>
        <s-stack direction="block" gap="2">
          <s-text-field
            label=""
            value={domain}
            placeholder="dein-shop.myshopify.com"
            onChange={(e) => {
              const ev = e as unknown as { target?: { value?: string }; detail?: { value?: string } };
              setDomain(ev.target?.value ?? ev.detail?.value ?? '');
            }}
          />
          <s-button variant="primary" onClick={handleConnect}>
            Shop verbinden
          </s-button>
        </s-stack>
        {error && (
          <s-paragraph tone="critical">{error}</s-paragraph>
        )}
      </s-stack>
    </s-banner>
  );
}
