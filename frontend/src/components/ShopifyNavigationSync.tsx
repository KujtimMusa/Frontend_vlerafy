'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * Lauscht auf shopify:navigate Events (von Polaris Web Components / App Bridge)
 * und synchronisiert diese mit dem Next.js Router.
 * Erforderlich für die CDN-basierte App Bridge 2025/2026.
 */
export function ShopifyNavigationSync({
  children,
}: {
  children?: React.ReactNode;
}) {
  const router = useRouter();

  useEffect(() => {
    const handleNavigate = (event: Event) => {
      const customEvent = event as CustomEvent<{ href?: string; target?: { href?: string } }>;
      const href = customEvent.detail?.href ?? customEvent.detail?.target?.href;
      if (href && typeof href === 'string' && href.startsWith('/')) {
        router.push(href);
      }
    };

    document.addEventListener('shopify:navigate', handleNavigate);
    return () => document.removeEventListener('shopify:navigate', handleNavigate);
  }, [router]);

  return children ? <>{children}</> : null;
}
