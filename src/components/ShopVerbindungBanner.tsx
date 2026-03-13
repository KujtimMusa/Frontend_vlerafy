'use client';

import { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Banner, TextField, Button, BlockStack, Text } from '@shopify/polaris';

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
    window.location.reload();
  };

  if (!show) return null;

  return (
    <Banner tone="warning" title="Shop nicht verbunden">
      <BlockStack gap="300">
        <Text as="p">
          Kein Shop wurde erkannt. Öffne die App über den Shopify Admin, oder
          gib deine Shop-Domain ein:
        </Text>
        <BlockStack gap="200">
          <TextField
            label=""
            value={domain}
            onChange={setDomain}
            placeholder="dein-shop.myshopify.com"
            error={error}
            autoComplete="off"
          />
          <Button variant="primary" onClick={handleConnect}>
            Shop verbinden
          </Button>
        </BlockStack>
      </BlockStack>
    </Banner>
  );
}
