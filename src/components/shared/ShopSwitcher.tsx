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
      window.location.reload();
    },
    onError: () => showToast('Fehler beim Wechseln', { isError: true }),
  });

  if (!shopsData?.shops?.length) return null;

  const activeId = String(shopsData.active_shop_id ?? '');

  return (
    <label>
      Aktiver Shop
      <select
        value={activeId}
        onChange={(e) => {
          const val = e.target.value;
          if (!val) return;
          const shop = shopsData.shops.find((s) => s.id === Number(val));
          if (shop)
            mutation.mutate({
              shopId: shop.id,
              useDemo: shop.type === 'demo',
            });
        }}
        disabled={mutation.isPending}
      >
        {shopsData.shops.map((s) => (
          <option key={s.id} value={String(s.id)}>
            {s.type === 'demo' ? `[Demo] ` : ''}
            {s.name}
          </option>
        ))}
      </select>
    </label>
  );
}
