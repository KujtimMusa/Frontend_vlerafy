'use client';

import { Suspense } from 'react';
import ShopInitializer from '@/components/ShopInitializer';
import { DashboardNav } from './DashboardNav';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Suspense fallback={null}>
      <ShopInitializer>
        <DashboardNav>{children}</DashboardNav>
      </ShopInitializer>
    </Suspense>
  );
}
