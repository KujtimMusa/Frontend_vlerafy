import { create } from 'zustand';
import type { Shop } from '@/types/models';

interface ShopStore {
  currentShop: Shop | null;
  shops: Shop[];
  setCurrentShop: (shop: Shop | null) => void;
  setShops: (shops: Shop[]) => void;
}

export const useShopStore = create<ShopStore>((set) => ({
  currentShop: null,
  shops: [],
  setCurrentShop: (shop) => set({ currentShop: shop }),
  setShops: (shops) => set({ shops }),
}));
