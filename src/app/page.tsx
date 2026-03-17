'use client';

import { Suspense, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

function HomePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const shop = searchParams.get('shop');
    const shopId = searchParams.get('shop_id');
    const host = searchParams.get('host');

    if (typeof window !== 'undefined') {
      // Immer speichern wenn vorhanden – auch wenn nur shop/host (öffnen aus Shopify Admin)
      if (shop) localStorage.setItem('shop_domain', shop);
      if (host) localStorage.setItem('shopify_host', host);
      if (shopId) {
        localStorage.setItem('shop_id', shopId);
        localStorage.setItem('current_shop_id', shopId);
      }
    }

    const idToken = searchParams.get('id_token');

    // shopId vorhanden = OAuth war erfolgreich, Shop in DB → direkt zum Dashboard
    if (shopId) {
      const q = new URLSearchParams([['shop', shop!], ['shop_id', shopId]]);
      if (host) q.set('host', host);
      if (idToken) q.set('id_token', idToken);
      router.replace(`/dashboard?${q.toString()}`);
      return;
    }

    // shop vorhanden OHNE shopId = User von Shopify Admin, Shop evtl. nicht in DB
    // → Top-Level-Redirect zu Install-Endpoint (OAuth erfordert Top-Level-Navigation)
    if (shop) {
      const installUrl =
        host
          ? `https://api.vlerafy.com/auth/shopify/install?shop=${encodeURIComponent(shop)}&host=${encodeURIComponent(host)}`
          : `https://api.vlerafy.com/auth/shopify/install?shop=${encodeURIComponent(shop)}`;
      // OAuth-Flow benötigt einen echten Top-Level-Redirect (kein SPA-Router).
      // App Bridge window.open würde den OAuth-Flow in einem Popup öffnen – nicht erlaubt.
      if (window.top) {
        window.top.location.href = installUrl;
      } else {
        window.location.href = installUrl;
      }
      return;
    }

    router.replace('/dashboard');
  }, [router, searchParams]);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <s-spinner />
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <s-spinner />
      </div>
    }>
      <HomePageContent />
    </Suspense>
  );
}
