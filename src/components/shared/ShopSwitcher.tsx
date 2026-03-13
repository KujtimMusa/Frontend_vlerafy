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

  const shops = shopsData?.shops?.filter((s) => s.type !== 'demo') ?? [];
  if (!shops.length) return null;

  const activeId = String(shopsData!.active_shop_id ?? '');
  const activeExists = shops.some((s) => String(s.id) === activeId);
  const displayValue = activeExists ? activeId : (activeId === '999' ? '999' : String(shops[0]?.id ?? ''));

  return (
    <label>
      Aktiver Shop
      <select
        value={displayValue}
        onChange={(e) => {
          const val = e.target.value;
          if (!val || val === '999') return;
          const shop = shops.find((s) => s.id === Number(val));
          if (shop)
            mutation.mutate({
              shopId: shop.id,
              useDemo: false,
            });
        }}
        disabled={mutation.isPending}
      >
        {!activeExists && activeId === '999' && (
          <option value="999">Bitte Shop verbinden</option>
        )}
        {shops.map((s) => (
          <option key={s.id} value={String(s.id)}>
            {s.name}
          </option>
        ))}
      </select>
    </label>
  );
}
