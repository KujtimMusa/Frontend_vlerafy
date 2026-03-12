"""
Shopify GraphQL Service
Ersetzt die deprecated REST API mit GraphQL für Produkte & Preise
"""

import httpx
import logging
from typing import List, Dict, Optional, Any
from app.config import settings

logger = logging.getLogger(__name__)


class ShopifyGraphQLService:
    """Shopify GraphQL API Client für Produkte & Preise"""
    
    def __init__(self, shop_url: str, access_token: str, api_version: str = None):
        """
        Initialisiert Shopify GraphQL Service
        
        Args:
            shop_url: Shopify Shop Domain (z.B. "my-shop.myshopify.com")
            access_token: Shopify Access Token
            api_version: API Version (default: aus settings)
        """
        # Entferne https:// falls vorhanden
        self.shop_url = shop_url.replace('https://', '').replace('http://', '').strip()
        self.access_token = access_token
        self.api_version = api_version or settings.SHOPIFY_API_VERSION
        
        # GraphQL Endpoint
        self.endpoint = f"https://{self.shop_url}/admin/api/{self.api_version}/graphql.json"
        
        self.headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json"
        }
        
        logger.info(f"Shopify GraphQL Service initialisiert für {self.shop_url}")
    
    async def execute_query(self, query: str, variables: Dict = None) -> Dict[str, Any]:
        """
        GraphQL Query/Mutation ausführen
        
        Args:
            query: GraphQL Query oder Mutation String
            variables: Variables für die Query
            
        Returns:
            Response JSON als Dict
            
        Raises:
            httpx.HTTPError: Bei HTTP-Fehlern
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.endpoint,
                    json=payload,
                    headers=self.headers
                )
                response.raise_for_status()
                
                result = response.json()
                
                # Prüfe auf GraphQL Errors
                if "errors" in result:
                    error_messages = [err.get("message", "Unknown error") for err in result["errors"]]
                    logger.error(f"GraphQL Errors: {error_messages}")
                    raise Exception(f"GraphQL Errors: {', '.join(error_messages)}")
                
                return result
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP Error bei GraphQL Request: {e}")
            raise
        except Exception as e:
            logger.error(f"Unerwarteter Fehler bei GraphQL Request: {e}")
            raise
    
    async def get_products(self, first: int = 50, after: Optional[str] = None) -> Dict[str, Any]:
        """
        Alle Produkte mit Varianten & Preisen holen
        
        Args:
            first: Anzahl Produkte pro Request (max 250)
            after: Cursor für Pagination
            
        Returns:
            Dict mit products.edges und pageInfo
        """
        query = """
        query getProducts($first: Int!, $after: String) {
          products(first: $first, after: $after) {
            edges {
              node {
                id
                title
                handle
                status
                vendor
                productType
                variants(first: 10) {
                  edges {
                    node {
                      id
                      price
                      compareAtPrice
                      sku
                      inventoryQuantity
                      title
                      barcode
                    }
                  }
                }
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        """
        
        variables = {"first": min(first, 250)}  # Shopify Limit: 250
        if after:
            variables["after"] = after
        
        result = await self.execute_query(query, variables)
        return result.get("data", {}).get("products", {})
    
    async def get_all_products(self, max_products: Optional[int] = None) -> List[Dict]:
        """
        Alle Produkte mit Pagination holen
        
        Args:
            max_products: Maximale Anzahl Produkte (None = alle)
            
        Returns:
            Liste aller Produkte
        """
        all_products = []
        has_next_page = True
        cursor = None
        
        while has_next_page:
            result = await self.get_products(first=250, after=cursor)
            
            edges = result.get("edges", [])
            all_products.extend([edge["node"] for edge in edges])
            
            page_info = result.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")
            
            # Stop bei max_products
            if max_products and len(all_products) >= max_products:
                break
        
        return all_products[:max_products] if max_products else all_products
    
    async def get_product_by_id(self, product_id: str) -> Optional[Dict]:
        """
        Einzelnes Produkt nach ID holen
        
        Args:
            product_id: Shopify Product ID (gid://shopify/Product/123456)
            
        Returns:
            Produkt-Dict oder None
        """
        query = """
        query getProduct($id: ID!) {
          product(id: $id) {
            id
            title
            handle
            status
            vendor
            productType
            variants(first: 10) {
              edges {
                node {
                  id
                  price
                  compareAtPrice
                  sku
                  inventoryQuantity
                  title
                  barcode
                }
              }
            }
          }
        }
        """
        
        # Stelle sicher, dass ID im richtigen Format ist
        if not product_id.startswith("gid://"):
            product_id = f"gid://shopify/Product/{product_id}"
        
        result = await self.execute_query(query, {"id": product_id})
        product = result.get("data", {}).get("product")
        
        return product
    
    async def update_variant_price(
        self, 
        variant_id: str, 
        new_price: float
    ) -> Dict[str, Any]:
        """
        Produktvarianten-Preis aktualisieren
        
        Args:
            variant_id: Shopify Variant ID (gid://shopify/ProductVariant/123456)
            new_price: Neuer Preis als Float
            
        Returns:
            Mutation Result mit productVariant und userErrors
        """
        mutation = """
        mutation updateVariantPrice($input: ProductVariantInput!) {
          productVariantUpdate(input: $input) {
            productVariant {
              id
              price
              compareAtPrice
            }
            userErrors {
              field
              message
            }
          }
        }
        """
        
        # Stelle sicher, dass ID im richtigen Format ist
        if not variant_id.startswith("gid://"):
            variant_id = f"gid://shopify/ProductVariant/{variant_id}"
        
        variables = {
            "input": {
                "id": variant_id,
                "price": str(new_price)  # Shopify erwartet String
            }
        }
        
        result = await self.execute_query(mutation, variables)
        return result.get("data", {}).get("productVariantUpdate", {})
    
    async def bulk_update_prices(
        self, 
        updates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Mehrere Preise gleichzeitig aktualisieren
        
        Args:
            updates: Liste von Dicts mit "variant_id" und "new_price"
            
        Returns:
            Liste von Mutation Results
        """
        results = []
        
        for update in updates:
            try:
                result = await self.update_variant_price(
                    update["variant_id"], 
                    update["new_price"]
                )
                results.append({
                    "variant_id": update["variant_id"],
                    "success": len(result.get("userErrors", [])) == 0,
                    "result": result
                })
            except Exception as e:
                logger.error(f"Fehler beim Update von Variant {update['variant_id']}: {e}")
                results.append({
                    "variant_id": update["variant_id"],
                    "success": False,
                    "error": str(e)
                })
        
        return results
    
    async def get_product_variant(self, variant_id: str) -> Optional[Dict]:
        """
        Einzelne Variante nach ID holen
        
        Args:
            variant_id: Shopify Variant ID
            
        Returns:
            Variant-Dict oder None
        """
        query = """
        query getVariant($id: ID!) {
          productVariant(id: $id) {
            id
            price
            compareAtPrice
            sku
            inventoryQuantity
            title
            barcode
            product {
              id
              title
            }
          }
        }
        """
        
        # Stelle sicher, dass ID im richtigen Format ist
        if not variant_id.startswith("gid://"):
            variant_id = f"gid://shopify/ProductVariant/{variant_id}"
        
        result = await self.execute_query(query, {"id": variant_id})
        variant = result.get("data", {}).get("productVariant")
        
        return variant


