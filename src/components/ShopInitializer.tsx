'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';

export default function ShopInitializer({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const searchParams = useSearchParams();

  useEffect(() => {
    // Sofort aus URL lesen BEVOR irgendein API Call stattfindet
    const shop =
      searchParams.get('shop') || new URLSearchParams(window.location.search).get('shop');
    const host =
      searchParams.get('host') || new URLSearchParams(window.location.search).get('host');
    const shopId =
      searchParams.get('shop_id') || new URLSearchParams(window.location.search).get('shop_id');

    if (shop) localStorage.setItem('shop_domain', shop);
    if (host) localStorage.setItem('shopify_host', host);
    if (shopId) {
      localStorage.setItem('shop_id', shopId);
      localStorage.setItem('current_shop_id', shopId);
    }

    setReady(true);
  }, [searchParams]);

  // Kein Render bis Shop-Daten gesetzt sind
  if (!ready) return null;

  return <>{children}</>;
}
