export interface Product {
  id: number;
  title: string;
  price: number;
  cost?: number;
  inventory: number;
  shopify_product_id: string;
  is_demo: boolean;
  image?: string;
  sku?: string;
  category?: string;
  shop_id?: number;
  created_at?: string;
  updated_at?: string;
}

export interface Shop {
  id: number;
  name: string;
  type: 'demo' | 'shopify';
  shop_url: string | null;
  product_count: number;
  is_active: boolean;
}

export interface ReasoningStrategy {
  price?: number;
  confidence?: number;
  strategy?: string;
  reasoning?: string;
}

export interface ReasoningObject {
  summary?: string;
  current_price?: number;
  recommended_price?: number;
  price_change_pct?: number;
  strategies?: {
    demand?: ReasoningStrategy;
    competitor?: ReasoningStrategy;
    inventory?: ReasoningStrategy;
    cost?: ReasoningStrategy;
    margin?: ReasoningStrategy;
  };
}

export interface Recommendation {
  id: number;
  product_id: number;
  product_name?: string;
  shop_id?: number;
  current_price: number;
  recommended_price: number;
  price_change_pct: number;
  confidence: number; // 0–1
  strategy: 'ML_OPTIMIZED' | 'FALLBACK_SAFE' | 'ERROR_FALLBACK' | string;
  reasoning: Record<string, unknown> | string;
  reasoning_object?: ReasoningObject;
  demand_growth?: number;
  days_of_stock?: number;
  sales_7d?: number;
  competitor_avg_price?: number;
  base_confidence?: number;
  ml_confidence?: number;
  ml_detector_confidence?: number;
  meta_labeler_confidence?: number;
  meta_labeler_approved?: boolean;
  confidence_label?: string;
  strategy_details?: StrategyDetail[];
  created_at: string;
  applied_at?: string | null;
}

export interface StrategyDetail {
  strategy: string;
  recommended_price: number;
  confidence: number;
  reasoning: string;
  competitor_context?: Record<string, unknown>;
}

export interface CompetitorPrice {
  source?: string;
  title?: string;
  competitor_name?: string;
  price: number;
  url?: string;
  competitor_url?: string;
  rating?: number;
  reviews?: number;
  scraped_at?: string;
}

export interface CompetitorSearchResponse {
  product_id: string;
  product_title: string;
  competitors: CompetitorPrice[];
  summary: {
    found: number;
    avg_price: number;
    min_price: number;
    max_price: number;
    your_position: 'cheapest' | 'below_average' | 'average' | 'above_average' | 'most_expensive' | 'unknown';
  };
  your_price: number;
  shop_context?: { is_demo: boolean; shop_id: number };
}

export interface CompetitorAnalysis {
  has_data: boolean;
  current_price: number;
  competitor_count: number;
  competitor_avg?: number;
  competitor_min?: number;
  competitor_max?: number;
  price_position: string;
  price_vs_avg_pct: number;
  competitors: CompetitorPrice[];
}

export interface ProductCostData {
  product_id: string;
  purchase_cost: number;
  shipping_cost: number;
  packaging_cost: number;
  payment_provider: string;
  payment_fee_percentage: number;
  payment_fee_fixed: number;
  country_code: string;
  category?: string;
  vat_rate?: number;
  last_updated?: string;
  created_at?: string;
}

export interface MarginCalculationResult {
  has_cost_data: boolean;
  selling_price: number;
  net_revenue: number;
  costs: {
    purchase: number;
    shipping: number;
    packaging: number;
    payment_fee: number;
    total_variable: number;
  };
  margin: {
    euro: number;
    percent: number;
  };
  break_even_price: number;
  recommended_min_price: number;
  is_above_break_even: boolean;
  is_above_min_margin: boolean;
  vat_rate: number;
  country_code: string;
  payment_provider: string;
}

export interface CategoryDefaults {
  category: string;
  typical_margin: number;
  shipping_estimate: number;
  packaging_estimate: number;
}

export interface DashboardStats {
  products_count: number;
  recommendations_pending: number;
  products_with_recommendations: number;
  recommendations_applied: number;
  missed_revenue: {
    total: number;
    product_count: number;
    recommendation_count: number;
    avg_per_product: number;
  };
  progress: {
    level: 'bronze' | 'silver' | 'gold' | 'platinum';
    points: number;
    next_level_points: number;
    points_needed: number;
    completed_steps: string[];
    pending_steps: { text: string; points: number; action: string }[];
  };
  next_steps: {
    urgent: boolean;
    title: string;
    description: string;
    action: string;
    href: string;
  }[];
}
