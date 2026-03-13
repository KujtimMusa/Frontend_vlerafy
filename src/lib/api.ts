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

// API-Backend (Railway). NIEMALS vlerafy.com – dort ist nur Frontend (Next.js).
// Fest auf Backend – NEXT_PUBLIC_API_URL ignoriert, da oft falsch konfiguriert.
export const API_URL = 'https://api.vlerafy.com';

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

function getSessionIdFromCookie(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(/session_id=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function getShopIdFromStorage(): string | null {
  if (typeof window === 'undefined') return null;
  return (
    localStorage.getItem('current_shop_id') ||
    localStorage.getItem('shop_id') ||
    null
  );
}

/** Session Token für Bearer Header – Priorität:
 *  1. id_token aus URL (Shopify übergibt beim Embedding: ?id_token=...)
 *  2. window.shopify.idToken() (App Bridge, max 2s Timeout) */
async function getSessionTokenForApi(): Promise<string | null> {
  if (typeof window === 'undefined') return null;

  // 1. id_token aus URL – sofort verfügbar, kein App-Bridge nötig
  const urlToken = new URLSearchParams(window.location.search).get('id_token');
  if (urlToken) return urlToken;

  // 2. App Bridge idToken (falls URL-Token fehlt)
  const timeout = new Promise<null>((resolve) => setTimeout(() => resolve(null), 2000));
  const tokenPromise = (async () => {
    try {
      if (window.shopify?.idToken) {
        const token = await window.shopify.idToken();
        if (token) return token;
      }
    } catch (e) {
      console.warn('[API] idToken failed, using fallback:', e);
    }
    return null;
  })();

  return Promise.race([tokenPromise, timeout]);
}

export async function getApiHeaders(): Promise<HeadersInit> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  const token = await getSessionTokenForApi();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Fix B: session_id + shop_id mitschicken
  const sessionId = getSessionIdFromCookie();
  if (sessionId) headers['X-Session-ID'] = sessionId;

  const shopId = getShopIdFromStorage();
  if (shopId) headers['X-Shop-ID'] = shopId;

  // X-Shop-Domain immer mitschicken wenn vorhanden (Fallback wenn Bearer fehlschlägt)
  if (typeof window !== 'undefined') {
    const shopDomain = localStorage.getItem('shop_domain');
    if (shopDomain) headers['X-Shop-Domain'] = shopDomain;
  }

  return headers;
}

/** Shop-Parameter für API-URL – Backend kann Shop auch aus Query erkennen (falls Cookies/Header blockiert)
 *  Priorität: ?shop=/?shop_id= aus AKTUELLER URL > localStorage */
function getShopParamsForUrl(): string {
  if (typeof window === 'undefined') return '';
  const urlParams = new URLSearchParams(window.location.search);
  const shopFromUrl = urlParams.get('shop');
  const shopIdFromUrl = urlParams.get('shop_id');

  const shop = shopFromUrl || localStorage.getItem('shop_domain') || '';
  const shopId = shopIdFromUrl || getShopIdFromStorage() || '';

  const params = new URLSearchParams();
  if (shopId) params.set('shop_id', shopId);
  else if (shop) params.set('shop', shop);

  return params.toString();
}

// ── Dashboard ──────────────────────────────────────────
export async function getDashboardStats(): Promise<DashboardStats> {
  const headers = await getApiHeaders();
  const params = getShopParamsForUrl();
  const url = params ? `${API_URL}/api/dashboard/stats?${params}` : `${API_URL}/api/dashboard/stats`;
  const res = await fetch(url, { headers, credentials: 'include' });
  if (!res.ok) throw new Error('Dashboard stats fehler');
  return res.json();
}

/** Redirect zu OAuth Install wenn Shop nicht in DB (401 oder Demo-Fallback). Gibt true zurück wenn Redirect ausgelöst. */
function redirectToOAuthInstallIfNeeded(res: Response): boolean {
  if (typeof window === 'undefined') return false;
  const shopDomain =
    new URLSearchParams(window.location.search).get('shop') ||
    localStorage.getItem('shop_domain') ||
    '';
  if (!shopDomain) return false;
  if (res.status === 401 || res.headers.get('X-Is-Demo') === 'true') {
    const host = new URLSearchParams(window.location.search).get('host') || '';
    const installUrl = host
      ? `https://api.vlerafy.com/auth/shopify/install?shop=${encodeURIComponent(shopDomain)}&host=${encodeURIComponent(host)}`
      : `https://api.vlerafy.com/auth/shopify/install?shop=${encodeURIComponent(shopDomain)}`;
    window.location.href = installUrl;
    return true;
  }
  return false;
}

// ── Products ───────────────────────────────────────────
export async function fetchProducts(shopId?: number): Promise<Product[]> {
  const headers = await getApiHeaders();
  const baseUrl = `${API_URL}/products/`;
  const params = shopId ? `shop_id=${shopId}` : getShopParamsForUrl();
  const url = params ? `${baseUrl}?${params}` : baseUrl;
  // Debug: Immer wenn params leer (Verdacht: Shop nicht erkannt)
  if (typeof window !== 'undefined') {
    const h = headers as Record<string, string>;
    if (!params || url === baseUrl || window.location.search.includes('debug=1')) {
      console.log('[API DEBUG] fetchProducts:', {
        url,
        params: params || '(LEER – Shop wird evtl. nicht erkannt)',
        hasBearer: !!h?.Authorization,
        urlShop: new URLSearchParams(window.location.search).get('shop'),
        lsShop: localStorage.getItem('shop_domain'),
      });
    }
  }
  const res = await fetch(url, { headers, credentials: 'include' });
  if (redirectToOAuthInstallIfNeeded(res)) return [];
  if (!res.ok) throw new Error('Produkte laden fehlgeschlagen');
  const data = await res.json();
  const products = Array.isArray(data) ? data : data.products ?? [];
  if (typeof window !== 'undefined' && window.location.search.includes('debug=1') && products.length === 0) {
    console.warn('[API DEBUG] Leere Antwort. Prüfe ob Backend Shop erkannt hat (Railway Logs).');
  }
  return products;
}

/** Produkte von Shopify in DB synchronisieren (z.B. bei erstem Öffnen falls OAuth-Sync fehlschlug) */
export async function syncProductsFromShopify(): Promise<{ synced: number; updated: number }> {
  const headers = await getApiHeaders();
  const params = getShopParamsForUrl();
  const url = params ? `${API_URL}/products/sync?${params}` : `${API_URL}/products/sync`;
  const res = await fetch(url, { method: 'POST', headers, credentials: 'include' });
  if (!res.ok) throw new Error('Produktsync fehlgeschlagen');
  const data = await res.json();
  return { synced: data.synced ?? 0, updated: data.updated ?? 0 };
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

export async function getRecommendationsList(
  status: 'pending' | 'applied' | 'all' = 'pending'
): Promise<{ recommendations: Array<{
  id: number;
  product_id: number;
  product_name: string;
  product_title: string;
  current_price: number;
  recommended_price: number;
  price_change_pct: number;
  confidence: number;
  strategy: string;
  reasoning: string;
  applied_at: string | null;
}> }> {
  const headers = await getApiHeaders();
  const params = getShopParamsForUrl();
  const url = `${API_URL}/recommendations/list?status=${status}${params ? `&${params}` : ''}`;
  const res = await fetch(url, { headers, credentials: 'include' });
  if (!res.ok) throw new Error('Empfehlungen laden fehlgeschlagen');
  return res.json();
}

export async function getMarginHistory(
  productId: string,
  days = 30
): Promise<{ product_id: string; days: number; history: Array<{ date: string; selling_price: number; margin_euro: number; margin_percent: number }> }> {
  const headers = await getApiHeaders();
  const params = getShopParamsForUrl();
  const url = `${API_URL}/margin/history/${productId}?days=${days}${params ? `&${params}` : ''}`;
  const res = await fetch(url, { headers, credentials: 'include' });
  if (!res.ok) throw new Error('Preishistorie laden fehlgeschlagen');
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
  const params = getShopParamsForUrl();
  const url = params ? `${API_URL}/shops?${params}` : `${API_URL}/shops`;
  const res = await fetch(url, { headers, credentials: 'include' });
  if (!res.ok) throw new Error('Shops laden fehlgeschlagen');
  return res.json();
}

export async function getCurrentShop() {
  const headers = await getApiHeaders();
  const params = getShopParamsForUrl();
  const url = params ? `${API_URL}/shops/current?${params}` : `${API_URL}/shops/current`;
  const res = await fetch(url, { headers, credentials: 'include' });
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
