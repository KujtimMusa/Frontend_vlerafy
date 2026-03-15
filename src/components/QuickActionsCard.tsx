'use client';

import { useRouter } from 'next/navigation';

interface QuickActionsCardProps {
  pendingCount: number;
  onSync: () => void;
  isSyncing: boolean;
  suffix: string;
}

export function QuickActionsCard({
  pendingCount,
  onSync,
  isSyncing,
  suffix,
}: QuickActionsCardProps) {
  const router = useRouter();
  return (
    <s-section>
      <s-stack direction="block" gap="4">
        <s-heading size="md">Schnellaktionen</s-heading>
        <s-stack direction="block" gap="3">
          <div style={{ width: '100%' }}>
            <s-button
              variant="primary"
              style={{ width: '100%' }}
              onClick={() => router.push(`/dashboard/pricing${suffix}`)}
            >
              {`${pendingCount} Preise optimieren`}
            </s-button>
          </div>
          <div style={{ width: '100%' }}>
            <s-button
              variant="secondary"
              onClick={onSync}
              loading={isSyncing}
              style={{ width: '100%' }}
            >
              Produkte synchronisieren
            </s-button>
          </div>
          <div style={{ width: '100%' }}>
            <s-button
              variant="plain"
              style={{ width: '100%' }}
              onClick={() => router.push(`/dashboard/analytics${suffix}`)}
            >
              Analysen anzeigen
            </s-button>
          </div>
        </s-stack>
      </s-stack>
    </s-section>
  );
}
