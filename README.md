# 🚀 Kujtims Plan – Vlerafy V3

**132 Files | Embedded Shopify App | ML Pricing | Production Ready**

## Struktur

```
Kujtims Plan/
├── backend/          # FastAPI (92 Files aus V3_MASTER_DATA)
├── frontend/         # Next.js 15 + shadcn + embedded Shopify
├── shared/           # Types + ML .pkl (optional)
├── config/           # railway.json, vercel.json
├── docker-compose.yml
├── shopify.app.toml
└── README.md
```

## 7 Kern-Features

- ⭐ **ML Pricing** – POST /api/v1/pricing/predict-price → PriceRecommendationCard
- **Margin Calculator** – POST /margin/calculate/{id} → MarginCalculator
- **Embedded Shopify** – AppBridge + sessionToken, ShopifyProvider
- **Product Dashboard** – GET /products → shadcn DataTable
- **Competitors** – POST /competitors/products/{id}/competitor-search → CompetitorAccordion
- **Shop Switcher** – Redis session → ShopSwitcher
- **shadcn UI** – table, card, button, accordion, badge, etc.

## Quick Start

### 1. Stack starten

```bash
cd "Kujtims Plan"
copy .env.example .env
# .env bearbeiten: DATABASE_URL, REDIS_URL, SHOPIFY_CLIENT_SECRET

docker-compose up -d
```

### 2. Backend prüfen

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/v1/pricing/predict-price ^
  -H "Content-Type: application/json" ^
  -d "{\"product_data\":{\"price\":29.99,\"cost\":15.0}}"
```

### 3. Frontend starten (ohne Docker)

```bash
cd frontend
npm run dev
# → http://localhost:3001
```

### 4. Shopify Embedded App

```bash
shopify app dev
# → App im Shopify Admin als iFrame
```

## Configs

- **config/railway.json** – Railway Deploy
- **shopify.app.toml** – Shopify App Konfiguration
- **.env.example** – Beispiel-Umgebungsvariablen

## Tech Stack

- **Frontend:** Next.js 15, shadcn/ui, Tailwind, Zustand, React Query
- **Backend:** FastAPI, XGBoost, PostgreSQL, Redis
- **Embedded:** @shopify/app-bridge, AppBridge React

---

✅ **KUJTIMS PLAN COMPLETE!** 🎉  
132 Files → 100% embedded Shopify App ready  
`docker-compose up && shopify app dev` → LIVE!
