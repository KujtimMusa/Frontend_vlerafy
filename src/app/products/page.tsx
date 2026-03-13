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
    const q = searchParams.toString();
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
