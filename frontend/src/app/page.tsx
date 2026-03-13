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

    if (shopId) {
      const dest = host ? `/dashboard?shop=${shop}&host=${host}&shop_id=${shopId}` : `/dashboard?shop_id=${shopId}`;
      router.replace(dest);
    } else if (shop) {
      // Ohne shop_id: trotzdem zu Dashboard – Backend löst shop über X-Shop-Domain
      router.replace(host ? `/dashboard?shop=${shop}&host=${host}` : `/dashboard?shop=${shop}`);
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
