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
    if (shopId) {
      const q = new URLSearchParams([['shop', shop!], ['shop_id', shopId]]);
      if (host) q.set('host', host);
      if (idToken) q.set('id_token', idToken);
      router.replace(`/dashboard?${q.toString()}`);
    } else if (shop) {
      const q = new URLSearchParams([['shop', shop]]);
      if (host) q.set('host', host);
      if (idToken) q.set('id_token', idToken);
      router.replace(`/dashboard?${q.toString()}`);
    } else {
      router.replace('/dashboard');
    }
  }, [router, searchParams]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-pulse text-slate-400">Lade Dashboard...</div>
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-slate-400">Lade Dashboard...</div>
      </div>
    }>
      <HomePageContent />
    </Suspense>
  );
}
