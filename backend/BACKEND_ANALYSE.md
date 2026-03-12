# Backend Analyse – Vlerafy

**Datum:** 12.03.2026

---

## 1. Projektstruktur

```
backend/
├── .gitignore
├── alembic.ini
├── Dockerfile
├── Procfile
├── railway.json
├── requirements.txt
├── start.sh
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_initial_tables.py
│       ├── 20260113_195255_add_sales_history_table.py
│       ├── 20260113_200000_add_price_history_table.py
│       ├── 20260113_203458_enhance_recommendation_model.py
│       ├── 20260130_155123_create_demo_shop.py
│       ├── add_competitor_prices.py
│       ├── add_margin_calculator.py
│       ├── add_oauth_fields_to_shop.py
│       ├── add_recommendation_metrics.py
│       ├── add_sales_30d_column.py
│       └── add_waitlist_table.py
├── app/
│   ├── __init__.py
│   ├── database.py
│   ├── dependencies.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── endpoints/
│   │           └── pricing_ml.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── feature_metadata.py
│   │   └── settings.py
│   ├── core/
│   │   ├── config_helper.py
│   │   ├── jwt_manager.py
│   │   ├── sentry_config.py
│   │   └── shop_context.py
│   ├── middleware/
│   │   └── rate_limiter.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── competitor.py
│   │   ├── margin.py
│   │   ├── price_history.py
│   │   ├── product.py
│   │   ├── recommendation.py
│   │   ├── sales_history.py
│   │   ├── shop.py
│   │   └── waitlist.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── auth.py
│   │   ├── backtest.py
│   │   ├── competitors.py
│   │   ├── dashboard.py
│   │   ├── debug.py
│   │   ├── demo_shop.py
│   │   ├── margin.py
│   │   ├── products.py
│   │   ├── recommendations.py
│   │   ├── shopify_routes.py
│   │   ├── shops.py
│   │   └── waitlist.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── competitive_strategy.py
│   │   ├── competitor_discovery.py
│   │   ├── competitor_price_service.py
│   │   ├── competitor_scraper.py
│   │   ├── confidence_analyzer.py
│   │   ├── confidence_calculator.py
│   │   ├── csv_demo_shop_adapter.py
│   │   ├── explainability/
│   │   │   ├── __init__.py
│   │   │   └── price_story_generator.py
│   │   ├── feature_engineering_service.py
│   │   ├── feature_inventory.py
│   │   ├── margin_calculator_service.py
│   │   ├── ml_monitoring_service.py
│   │   ├── ml_pricing_service.py
│   │   ├── mvp_confidence_calculator.py
│   │   ├── price_history_service.py
│   │   ├── pricing_engine.py
│   │   ├── pricing_factors.py
│   │   ├── pricing_orchestrator.py
│   │   ├── recommendation_service.py
│   │   ├── sales_history_service.py
│   │   ├── shop_adapter_factory.py
│   │   ├── shopify_adapter.py
│   │   ├── shopify_error_handler.py
│   │   ├── shopify_graphql_service.py
│   │   ├── shopify_product_service.py
│   │   ├── shopify_rate_limiter.py
│   │   ├── shopify_variant_detector.py
│   │   └── ml/
│   │       ├── __init__.py
│   │       ├── ecommerce_data_loader.py
│   │       ├── feature_schema.py
│   │       ├── kaggle_data_loader.py
│   │       ├── kaggle_history_loader.py
│   │       ├── ml_pricing_engine.py
│   │       ├── model_config.py
│   │       ├── price_features.py
│   │       └── train_ml_models.py
│   ├── tasks/
│   │   ├── celery_app.py
│   │   ├── competitor_tasks.py
│   │   ├── ml_tasks.py
│   │   └── pricing_tasks.py
│   └── utils/
│       ├── __init__.py
│       ├── admin_auth.py
│       ├── datetime_helpers.py
│       ├── encryption.py
│       ├── logging_utils.py
│       └── oauth.py
├── data/
│   └── demo_products.csv
└── ml_models/
    ├── meta_labeler_v1.0_production.pkl
    └── xgboost_v1.2_tuned.pkl
```

---

## 2. Auth & OAuth Flow

### Dateien für Shopify OAuth

| Datei | Zweck |
|-------|-------|
| `app/routers/auth.py` | OAuth Install, Callback, Status, Refresh |
| `app/utils/oauth.py` | generate_install_url, verify_hmac, exchange_code_for_token |
| `app/utils/encryption.py` | encrypt_token, decrypt_token |

### Access Token Speicherung

**Speicherort:** PostgreSQL-Tabelle `shops`

- Feld: `access_token` (String, nullable)
- Verschlüsselung: `encrypt_token()` vor dem Speichern, `decrypt_token()` beim Lesen
- Nutzung: `app.utils.encryption` (Fernet)

### Session Token vom Frontend

**Keine Validierung eines Shopify Session Tokens im Backend.**

- Das Frontend nutzt `X-Session-ID` oder `session_id` Cookie für Session-Kontext
- `Authorization: Bearer <JWT>` wird in `dependencies.get_current_shop` geprüft (JWT, kein Shopify Session Token)
- Ein Shopify App-Bridge-Session-Token wird nicht geprüft

### Relevante Zeilen aus auth.py

```python
# Zeilen 24-25: OAuth State (In-Memory)
oauth_states = {}

# Zeilen 66-84: Token Exchange
token_url = f"https://{shop}/admin/oauth/access_token"
token_data = {
    "client_id": settings.SHOPIFY_CLIENT_ID,
    "client_secret": settings.SHOPIFY_CLIENT_SECRET,
    "code": code
}
response = requests.post(token_url, json=token_data)
token_response = response.json()
access_token = token_response.get("access_token")

# Zeilen 129-155: Token speichern in DB (verschlüsselt)
encrypted_token = encrypt_token(access_token)
existing_shop.access_token = encrypted_token
# oder
shop_obj = Shop(..., access_token=encrypted_token, ...)

# Zeilen 311-334: JWT Cookies nach OAuth (shopify/callback)
response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, samesite="none", max_age=24*60*60)
response.set_cookie(key="refresh_token", value=refresh_token, ...)
```

---

## 3. Shop & Session Handling

### shop_id Durchreichung

1. **ShopContext (Session-basiert):** `session_id` → Redis/Memory → `active_shop_id`
2. **JWT:** `get_current_shop` liest `shop_id` aus JWT Payload

### shop_context.py – Funktionsweise

**Datei:** `app/core/shop_context.py`

| Element | Beschreibung |
|--------|--------------|
| Session-ID Quelle | `get_session_id()`: Cookie `session_id` → Header `X-Session-ID` → Fallback: MD5(IP:User-Agent) |
| Redis Keys | `session:{session_id}:active_shop_id`, `session:{session_id}:demo_mode` |
| TTL | 7 Tage (`expire=86400*7`) |
| Fallback | In-Memory `_memory_store`, wenn Redis fehlt |

**Kernlogik (Auszug):**

```python
# Zeilen 268-291: Session-ID Extraktion
def get_session_id(request: Request) -> str:
    session_id = request.cookies.get("session_id")
    if session_id: return session_id
    session_id = request.headers.get("X-Session-ID")
    if session_id: return session_id
    # Fallback: Hash aus IP + User-Agent
    hash_input = f"{client_ip}:{user_agent}"
    return hashlib.md5(hash_input.encode()).hexdigest()[:16]
```

```python
# Zeilen 127-136: Default Shop
@property
def active_shop_id(self) -> int:
    shop_id = self._get(self._cache_key_shop, 999)  # Default: Demo Shop
    return int(shop_id) if shop_id else 999
```

### Aktueller Shop pro Request

- **ShopContext:** Aus Redis/Memory über `session_id` → `active_shop_id`
- **JWT-Auth:** Aus Token Payload `shop_id`
- **Query-Parameter:** `shop_id` (nur Dev-Modus in `get_current_shop`)

---

## 4. API Endpoints – Auth-relevante Routes

### X-Session-ID Header

Wird von `shop_context.get_session_id()` genutzt. Damit nutzen alle Routen mit `Depends(get_shop_context)` den Session-Kontext:

- `shops` (get_shop_context)
- `dashboard` (get_shop_context)
- `recommendations` (get_shop_context)
- `products` (teils get_db nur)
- `shopify_routes` (get_shop_context)
- `competitors` (get_shop_context)
- `margin` (get_shop_context)

### Authorization: Bearer Token (JWT)

Erwartet von `get_current_shop()` und `get_current_admin()`:

- `admin.py`: `get_current_admin` (HTTPBearer)
- `waitlist.py`: `get_current_admin` für Admin-Route
- `margin.py`: `get_current_shop_optional` (optional)

Reihenfolge in `get_current_shop` (dependencies.py):

1. JWT aus Cookie `access_token`
2. JWT aus Header `Authorization: Bearer <token>`
3. Cookie `shop_id` (Legacy)
4. Query-Parameter `shop_id` (nur Dev)

### Öffentliche Endpoints (ohne Auth)

| Endpoint | Datei |
|----------|-------|
| `/` | main.py |
| `/health` | main.py |
| `/api/status` | main.py |
| `/debug/sentry-test` | main.py |
| `/auth/shopify/install` | auth.py |
| `/auth/shopify/callback` | auth.py |
| `/auth/shopify/status` | auth.py |
| `/auth/shopify/refresh` | auth.py (Cookie) |
| `/api/demo-shop/*` | demo_shop.py |
| `/api/waitlist/` (POST) | waitlist.py |
| `/api/v1/pricing/*` | pricing_ml.py |
| `/products/` (GET) | products.py |
| `/competitors/*` (mehrere) | competitors.py |
| `/backtest/*` | backtest.py |
| `/debug/*` | debug.py |

### getApiHeaders() Logik (Backend)

Es gibt keine `getApiHeaders`-Funktion im Backend. Die Logik liegt im Frontend in `lib/api.ts`. Dort wird u.a. gesetzt:

- `Authorization: Bearer ${sessionToken}` wenn vorhanden
- `X-Session-ID` (aus localStorage) als Fallback

---

## 5. Shopify API Calls

### Services mit direkten Shopify API Aufrufen

| Service | Methode |
|---------|---------|
| `shopify_adapter.py` | shopifyapi (REST) |
| `shopify_graphql_service.py` | httpx → GraphQL |
| `shopify_product_service.py` | httpx (nutzt evtl. unverschlüsselten Token – Hinweis) |

### Access Token für Shopify API

1. **shop_context.get_adapter():** Liest Shop aus DB, entschlüsselt `access_token`, übergibt an Adapter
2. **Direkte Nutzung:** z.B. `shopify_routes.py`, `products.py` – `decrypt_token(shop.access_token)` vor Aufruf

### shopify_product_service.py (Zeilen 40-74)

```python
def _get_shop_credentials(self, shop_id: str) -> Optional[Dict]:
    shop = db.query(Shop).filter(...).first()
    if not shop or not shop.access_token:
        return None
    return {
        'access_token': shop.access_token,  # ACHTUNG: Verschlüsselt!
        'shop_domain': shop_domain
    }
```

Hinweis: `_get_shop_credentials` liefert den verschlüsselten Token; für echte Shopify-Aufrufe muss vorher `decrypt_token` verwendet werden. Aktuell wird dieser Service von den Routen nicht direkt genutzt.

### shopify_graphql_service.py (Zeilen 17-38)

```python
def __init__(self, shop_url: str, access_token: str, api_version: str = None):
    self.shop_url = shop_url.replace('https://', '').strip()
    self.access_token = access_token  # Erwartet entschlüsselten Token
    self.endpoint = f"https://{self.shop_url}/admin/api/{api_version}/graphql.json"
    self.headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }
```

Der Token wird von den Aufrufern (z.B. shopify_routes, products) nach `decrypt_token()` übergeben.

---

## 6. Datenbank – Shop Tabelle

### Shop Model (app/models/shop.py)

```python
class Shop(Base):
    __tablename__ = "shops"

    id = Column(Integer, primary_key=True, index=True)
    shop_url = Column(String, unique=True, index=True, nullable=False)
    access_token = Column(String, nullable=True)  # Verschlüsselt
    scope = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    shop_name = Column(String, nullable=True)
    installed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

### Auth-relevante Felder

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `access_token` | String (nullable) | Verschlüsselter Shopify Access Token |
| `scope` | String (nullable) | OAuth Scopes (z.B. read_products, write_products) |
| `is_active` | Boolean | Shop installiert und aktiv |
| `installed_at` | DateTime | Installationszeitpunkt |

Es gibt keine Felder für: `session_token`, `host` (nur OAuth-State temporär in Memory).

---

## 7. Redis/Session

### Verwendung

| Zweck | Implementierung |
|------|-----------------|
| Shop-Kontext | `ShopContext` – `active_shop_id`, `is_demo_mode` pro Session |
| Celery | Broker und Backend |

### Redis Keys & TTL

| Key | Wert | TTL |
|-----|------|-----|
| `session:{session_id}:active_shop_id` | Shop-ID (int) | 7 Tage |
| `session:{session_id}:demo_mode` | true/false | 7 Tage |

### Fallback

- Ohne Redis oder bei Fehlern: In-Memory `_memory_store`
- Bei `redis://redis:` oder `redis://localhost:`: Redis wird als nicht konfiguriert betrachtet → In-Memory

---

## 8. Environment Variables

### SHOPIFY_* Variablen (aus settings.py / .env)

| Variable | Quelle | Default |
|----------|--------|---------|
| `SHOPIFY_CLIENT_ID` | settings.py | "" |
| `SHOPIFY_CLIENT_SECRET` | settings.py | "" |
| `SHOPIFY_API_SCOPES` | settings.py | "read_products,write_products" |
| `SHOPIFY_REDIRECT_URI` | settings.py | "https://api.vlerafy.com/auth/shopify/callback" |
| `SHOPIFY_APP_URL` | settings.py | "https://api.vlerafy.com" |
| `SHOPIFY_APP_NAME` | settings.py | "Vlerafy" |
| `SHOPIFY_API_VERSION` | settings.py | "2024-10" |

### Laden

- **Hauptquelle:** `app.config.settings.Settings` (pydantic-settings, `BaseSettings`)
- **Config:** `env_file = ".env"`, `case_sensitive = False`
- **JWT/Admin:** Teilweise Fallback über `os.getenv()` (z.B. in jwt_manager, admin_auth)

---

## 9. CORS & Middleware

### Erlaubte Origins (main.py, Zeilen 283-302)

```python
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://vlerafy.com",
    "https://www.vlerafy.com",
    "https://*.myshopify.com",
]
# Plus FRONTEND_URL aus Environment
```

### Middleware

| Middleware | Datei | Funktion |
|------------|-------|----------|
| Request Logging | main.py | Dauer und Pfad pro Request |
| CORS | main.py | CORSMiddleware |
| Rate Limiting | middleware/rate_limiter.py | slowapi, 1000/h global, 100/min pro Shop |

### Rate Limiting Keys

- Global: `get_remote_address`
- Pro Shop: JWT aus Cookie/Header → `shop_id` oder IP als Fallback

---

## 10. Celery / Background Jobs

### Tasks

| Task | Datei | Beschreibung |
|------|-------|--------------|
| `retrain_ml_models` | ml_tasks.py | Wöchentlich (Sonntag 2:00 UTC) |
| `monitor_ml_performance` | ml_tasks.py | Täglich 3:00 UTC |
| `update_competitor_prices` | competitor_tasks.py | Täglich 3:00 UTC |
| `retry_failed_scrapes` | competitor_tasks.py | Täglich 6:00 UTC |
| `auto_discover_competitors_daily` | competitor_tasks.py | Täglich 4:00 UTC |

### Shop-Spezifika

| Task | Shop-Bezug |
|------|------------|
| `update_competitor_prices` | Iteriert alle `CompetitorPrice`, kein shop_id |
| `retrain_ml_models` | Nutzt `Recommendation`, kein expliziter shop_id |
| `retry_failed_scrapes` | Basiert auf CompetitorPrice |
| `auto_discover_competitors_daily` | Sichtet DB-Records |

Es werden keine `shop_id`-Argumente an die geplanten Tasks übergeben; sie arbeiten auf globalen DB-Daten.
