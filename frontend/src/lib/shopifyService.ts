import { API_URL, getApiHeaders } from './api';

export interface ApplyPriceRequest {
  product_id: number;
  recommended_price: number;
  recommendation_id?: number;
  variant_id?: string;
}

export interface ApplyPriceResponse {
  success: boolean;
  message: string;
  new_price: number;
  variant_id: string;
  product_id: number;
}

export async function applyRecommendedPrice(
  request: ApplyPriceRequest
): Promise<ApplyPriceResponse> {
  const headers = await getApiHeaders();
  const r = await fetch(`${API_URL}/api/shopify/apply-price`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify(request),
  });
  if (!r.ok) throw new Error((await r.json()).detail || 'Preis anwenden fehlgeschlagen');
  return r.json();
}
