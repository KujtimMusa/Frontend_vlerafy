import type {
  Product,
  Shop,
  Recommendation,
  CompetitorSearchResponse,
  CompetitorAnalysis,
  ProductCostData,
  MarginCalculationResult,
  CategoryDefaults,
  DashboardStats,
} from '@/types/models';

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.vlerafy.com';

declare global {
  interface Window {
    shopify?: {
      idToken: () => Promise<string>;
      toast: {
        show: (message: string, options?: { duration?: number; isError?: boolean }) => void;
      };
    };
  }
}

export async function getApiHeaders(): Promise<HeadersInit> {
  try {
    if (typeof window !== 'undefined' && window.shopify?.idToken) {
      const token = await window.shopify.idToken();
      return {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      };
    }
  } catch {
    // Fallback wenn kein Token (z.B. Dev außerhalb Embedded App)
  }
  return { 'Content-Type': 'application/json' };
}

// ── Dashboard ──────────────────────────────────────────
export async function getDashboardStats(): Promise<DashboardStats> {
  const headers = await getApiHeaders();
  const res = await fetch(`${API_URL}/api/dashboard/stats`, {
    headers,
    credentials: 'include',
  });
  if (!res.ok) throw new Error('Dashboard stats fehler');
  return res.json();
}

// ── Products ───────────────────────────────────────────
export async function fetchProducts(shopId?: number): Promise<Product[]> {
  const headers = await getApiHeaders();
  const url = shopId ? `${API_URL}/products/?shop_id=${shopId}` : `${API_URL}/products/`;
  const res = await fetch(url, { headers, credentials: 'include' });
  if (!res.ok) throw new Error('Produkte laden fehlgeschlagen');
  const data = await res.json();
  return Array.isArray(data) ? data : data.products ?? [];
}

// ── Recommendations ────────────────────────────────────
export async function getRecommendation(
  productId: number
): Promise<Recommendation | null> {
  const headers = await getApiHeaders();
  const res = await fetch(
    `${API_URL}/recommendations/product/${productId}`,
    { headers, credentials: 'include' }
  );
  if (!res.ok) return null;
  const data = await res.json();
  return data.recommendations?.[0] ?? null;
}

export async function generateRecommendation(
  productId: number
): Promise<Recommendation> {
  const headers = await getApiHeaders();
  const res = await fetch(
    `${API_URL}/recommendations/generate/${productId}`,
    { method: 'POST', headers, credentials: 'include' }
  );
  if (!res.ok) throw new Error('Empfehlung generieren fehlgeschlagen');
  const data = await res.json();
  return data.recommendation;
}

export async function acceptRecommendation(id: number) {
  const headers = await getApiHeaders();
  return fetch(`${API_URL}/recommendations/${id}/accept`, {
    method: 'PATCH',
    headers,
    credentials: 'include',
  });
}

export async function rejectRecommendation(id: number, reason?: string) {
  const headers = await getApiHeaders();
  return fetch(`${API_URL}/recommendations/${id}/reject`, {
    method: 'PATCH',
    headers,
    credentials: 'include',
    body: JSON.stringify({ reason: reason ?? '' }),
  });
}

export async function markRecommendationApplied(id: number) {
  const headers = await getApiHeaders();
  return fetch(`${API_URL}/recommendations/${id}/mark-applied`, {
    method: 'PATCH',
    headers,
    credentials: 'include',
  });
}

export async function getEngineStatus() {
  const headers = await getApiHeaders();
  const res = await fetch(`${API_URL}/recommendations/engine-status`, {
    headers,
    credentials: 'include',
  });
  return res.json();
}

// ── ML Pricing ─────────────────────────────────────────
export async function predictPrice(
  productId: number,
  confidenceThreshold = 0.6
) {
  const headers = await getApiHeaders();
  const res = await fetch(`${API_URL}/api/v1/pricing/predict-price`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify({
      product_id: productId,
      confidence_threshold: confidenceThreshold,
    }),
  });
  if (!res.ok) throw new Error('ML Prediction fehlgeschlagen');
  return res.json();
}

// ── Margin ─────────────────────────────────────────────
export async function getProductCosts(
  productId: string
): Promise<ProductCostData | null> {
  const headers = await getApiHeaders();
  const res = await fetch(`${API_URL}/margin/costs/${productId}`, {
    headers,
    credentials: 'include',
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error('Kostendaten laden fehlgeschlagen');
  return res.json();
}

export async function hasProductCosts(productId: string): Promise<boolean> {
  const headers = await getApiHeaders();
  const res = await fetch(`${API_URL}/margin/has-costs/${productId}`, {
    headers,
    credentials: 'include',
  });
  const data = await res.json();
  return data.has_cost_data ?? false;
}

export async function saveProductCosts(
  costs: Omit<ProductCostData, 'last_updated' | 'created_at' | 'vat_rate'>
) {
  const headers = await getApiHeaders();
  const res = await fetch(`${API_URL}/margin/costs`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify(costs),
  });
  if (!res.ok) throw new Error('Kostendaten speichern fehlgeschlagen');
  return res.json();
}

export async function updateProductCosts(
  productId: string,
  costs: Partial<ProductCostData>
) {
  const headers = await getApiHeaders();
  return fetch(`${API_URL}/margin/costs/${productId}`, {
    method: 'PUT',
    headers,
    credentials: 'include',
    body: JSON.stringify(costs),
  });
}

export async function calculateMargin(
  productId: string,
  sellingPrice: number
): Promise<MarginCalculationResult> {
  const headers = await getApiHeaders();
  const res = await fetch(
    `${API_URL}/margin/calculate/${productId}`,
    {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify({ selling_price: sellingPrice }),
    }
  );
  if (!res.ok) throw new Error('Margenberechnung fehlgeschlagen');
  return res.json();
}

export async function getCategoryDefaults(
  category: string
): Promise<CategoryDefaults> {
  const headers = await getApiHeaders();
  const res = await fetch(
    `${API_URL}/margin/category-defaults/${category}`,
    { headers, credentials: 'include' }
  );
  return res.json();
}

// ── Competitors ────────────────────────────────────────
export async function searchCompetitors(
  productId: number | string,
  maxResults = 5
): Promise<CompetitorSearchResponse> {
  const headers = await getApiHeaders();
  const res = await fetch(
    `${API_URL}/competitors/products/${productId}/competitor-search?max_results=${maxResults}`,
    { method: 'POST', headers, credentials: 'include' }
  );
  if (!res.ok) throw new Error('Competitor Search fehlgeschlagen');
  return res.json();
}

export async function getCompetitorAnalysis(
  productId: number
): Promise<CompetitorAnalysis> {
  const headers = await getApiHeaders();
  const res = await fetch(
    `${API_URL}/competitors/products/${productId}/analysis`,
    { headers, credentials: 'include' }
  );
  if (!res.ok) throw new Error('Competitor Analyse fehlgeschlagen');
  return res.json();
}

export async function autoDiscoverCompetitors(productId: number | string) {
  const headers = await getApiHeaders();
  return fetch(
    `${API_URL}/competitors/products/${productId}/auto-discover`,
    { method: 'POST', headers, credentials: 'include' }
  );
}

// ── Shopify ────────────────────────────────────────────
export async function applyPrice(productId: number, price: number) {
  const headers = await getApiHeaders();
  const res = await fetch(`${API_URL}/api/shopify/apply-price`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify({ product_id: productId, recommended_price: price }),
  });
  if (!res.ok) throw new Error('Preis übernehmen fehlgeschlagen');
  return res.json();
}

// ── Shops ──────────────────────────────────────────────
export async function getAvailableShops(): Promise<{
  shops: Shop[];
  active_shop_id: number;
  is_demo_mode: boolean;
}> {
  const headers = await getApiHeaders();
  const res = await fetch(`${API_URL}/shops`, {
    headers,
    credentials: 'include',
  });
  if (!res.ok) throw new Error('Shops laden fehlgeschlagen');
  return res.json();
}

export async function getCurrentShop() {
  const headers = await getApiHeaders();
  const res = await fetch(`${API_URL}/shops/current`, {
    headers,
    credentials: 'include',
  });
  return res.json();
}

export async function switchShop(shopId: number, useDemo: boolean) {
  const headers = await getApiHeaders();
  return fetch(`${API_URL}/shops/switch`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify({ shop_id: shopId, use_demo: useDemo }),
  });
}
