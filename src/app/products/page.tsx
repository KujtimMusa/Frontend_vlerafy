'use client';

import { Suspense, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

/**
 * Redirect /products → /dashboard/products
 * Fix: Polaris/App Bridge navigiert manchmal zu /products statt /dashboard/products
 */
function ProductsRedirectContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    let q = searchParams.toString();
    if (!q && typeof window !== 'undefined') {
      const p = new URLSearchParams();
      const shop = localStorage.getItem('shop_domain');
      const host = localStorage.getItem('shopify_host');
      const shopId = localStorage.getItem('current_shop_id');
      if (shop) p.set('shop', shop);
      if (host) p.set('host', host);
      if (shopId) p.set('shop_id', shopId);
      q = p.toString();
    }
    const dest = q ? `/dashboard/products?${q}` : '/dashboard/products';
    router.replace(dest);
  }, [router, searchParams]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-pulse text-slate-400">Weiterleitung...</div>
    </div>
  );
}

export default function ProductsRedirectPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center animate-pulse text-slate-400">Lade...</div>}>
      <ProductsRedirectContent />
    </Suspense>
  );
}
