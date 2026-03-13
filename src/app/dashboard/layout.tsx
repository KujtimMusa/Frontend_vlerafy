'use client';

import { Suspense } from 'react';
import { DashboardNav } from './DashboardNav';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Suspense fallback={<div className="p-4 animate-pulse text-slate-400">Lade...</div>}>
      <DashboardNav>{children}</DashboardNav>
    </Suspense>
  );
}
