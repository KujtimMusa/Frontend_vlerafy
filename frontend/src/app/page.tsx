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

    if (shopId) {
      if (typeof window !== 'undefined') {
        localStorage.setItem('shop_id', shopId);
        localStorage.setItem('current_shop_id', shopId);
      }
      const dest = host ? `/dashboard?shop=${shop}&host=${host}&shop_id=${shopId}` : `/dashboard?shop_id=${shopId}`;
      router.replace(dest);
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
