'use client';

import { Suspense } from 'react';
import ShopInitializer from '@/components/ShopInitializer';
import { ShopVerbindungBanner } from '@/components/ShopVerbindungBanner';

// ✅ BFS [Punkt 1] erledigt — Sidebar entfernt, kein DashboardNav mehr
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Suspense fallback={null}>
      <ShopInitializer>
        <main className="vlerafy-main">
          <s-stack direction="block" gap="4">
            <ShopVerbindungBanner />
            <s-box padding="2">{children}</s-box>
          </s-stack>
        </main>
      </ShopInitializer>
    </Suspense>
  );
}
