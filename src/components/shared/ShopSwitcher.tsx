'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getAvailableShops, switchShop } from '@/lib/api';
import { showToast } from '@/lib/toast';

export function ShopSwitcher() {
  const qc = useQueryClient();
  const { data: shopsData } = useQuery({
    queryKey: ['shops'],
    queryFn: getAvailableShops,
  });

  const mutation = useMutation({
    mutationFn: ({ shopId, useDemo }: { shopId: number; useDemo: boolean }) =>
      switchShop(shopId, useDemo),
    onSuccess: () => {
      showToast('Shop gewechselt', { duration: 2000 });
      qc.invalidateQueries({ queryKey: ['shops'] });
      qc.invalidateQueries({ queryKey: ['products'] });
      qc.invalidateQueries({ queryKey: ['dashboard-stats'] });
      qc.invalidateQueries({ queryKey: ['recommendations'] });
    },
    onError: () => showToast('Fehler beim Wechseln', { isError: true }),
  });

  const shops = shopsData?.shops?.filter((s) => s.type !== 'demo') ?? [];
  if (!shops.length) return null;

  const activeId = String(shopsData!.active_shop_id ?? '');
  const activeExists = shops.some((s) => String(s.id) === activeId);
  const displayValue = activeExists ? activeId : (activeId === '999' ? '999' : String(shops[0]?.id ?? ''));

  const options = [
    ...(!activeExists && activeId === '999' ? [{ label: 'Bitte Shop verbinden', value: '999' }] : []),
    ...shops.map((s) => ({ label: s.name, value: String(s.id) })),
  ];

  return (
    <s-select
      label="Aktiver Shop"
      value={displayValue}
      options={JSON.stringify(options)}
      disabled={mutation.isPending}
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      onChange={(e: any) => {
        const val = e?.target?.value ?? e?.detail?.value ?? '';
        if (!val || val === '999') return;
        const shop = shops.find((s) => s.id === Number(val));
        if (shop) mutation.mutate({ shopId: shop.id, useDemo: false });
      }}
    />
  );
}
