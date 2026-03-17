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
        <ShopVerbindungBanner />
        {children}
      </ShopInitializer>
    </Suspense>
  );
}
