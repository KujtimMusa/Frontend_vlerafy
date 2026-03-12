import { create } from 'zustand';

interface User {
  id: number;
  name: string;
  email: string | null;
}

interface AuthState {
  user: User | null;
  shopId: string | null;
  setShopId: (id: string) => void;
  setUser: (user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  shopId: null,
  setShopId: (id) => set({ shopId: id }),
  setUser: (user) => set({ user }),
  logout: () => set({ user: null, shopId: null }),
}));
