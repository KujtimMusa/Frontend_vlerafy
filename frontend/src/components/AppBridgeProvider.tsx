'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';

/**
 * App Bridge v4: Host-Caching für Session Token & Navigation.
 * Das eigentliche App Bridge wird über app-bridge.js im Layout geladen.
 * Host aus URL cachen, damit er nach Navigation verfügbar bleibt.
 */
function AppBridgeHostCache({ children }: { children: React.ReactNode }) {
  const searchParams = useSearchParams();
  const host =
    searchParams.get('host') ??
    (typeof window !== 'undefined' ? localStorage.getItem('shopify_host') ?? '' : '');

  if (host && typeof window !== 'undefined') {
    localStorage.setItem('shopify_host', host);
  }

  return <>{children}</>;
}

export default function AppBridgeProvider({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<>{children}</>}>
      <AppBridgeHostCache>{children}</AppBridgeHostCache>
    </Suspense>
  );
}
