"""
Dashboard Stats API
Berechnet Missed Revenue und Trust Ladder für Dashboard
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import logging

from app.database import get_db
from app.core.shop_context import get_shop_context, ShopContext
from app.models.recommendation import Recommendation
from app.models.product import Product

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
logger = logging.getLogger(__name__)


@router.get("/stats")
async def get_dashboard_stats(
    request: Request,
    db: Session = Depends(get_db),
    shop_context: ShopContext = Depends(get_shop_context)
):
    """
    Dashboard Stats für Missed Revenue & Trust Ladder
    """
    from app.core.shop_context import get_session_id
    
    session_id = get_session_id(request)
    
    logger.info(f"[STATS] ========== GET DASHBOARD STATS ==========")
    logger.info(f"[STATS] Session ID: {session_id}")
    logger.info(f"[STATS] Context BEFORE reload: shop_id={shop_context.active_shop_id}, is_demo={shop_context.is_demo_mode}")
    
    # ✅ CRITICAL: Force reload from Redis/Memory
    shop_context.load()
    
    logger.info(f"[STATS] Context AFTER reload: shop_id={shop_context.active_shop_id}, is_demo={shop_context.is_demo_mode}")
    
    shop_id = shop_context.active_shop_id
    is_demo = shop_context.is_demo_mode
    
    logger.info(f"📊 Dashboard Stats für Shop {shop_id} (Demo: {is_demo})")
    
    # ============================================
    # 1. BASIC COUNTS
    # ============================================
    products_count = db.query(Product).filter(
        Product.shop_id == shop_id
    ).count()
    
    logger.info(f"[STATS] Found {products_count} products for shop_id={shop_id}")
    
    # Status aus applied_at ableiten
    # ✅ FIX: Nur neueste Empfehlung pro Produkt anzeigen (verhindert 166 Empfehlungen bei 20 Produkten)
    # Subquery: Neueste Empfehlung pro Produkt
    subq = db.query(
        Recommendation.product_id,
        func.max(Recommendation.created_at).label('max_created')
    ).filter(
        Recommendation.shop_id == shop_id,
        Recommendation.is_demo == is_demo,
        Recommendation.applied_at.is_(None)  # PENDING
    ).group_by(Recommendation.product_id).subquery()
    
    # Main Query: Join mit subquery - nur neueste Empfehlung pro Produkt
    pending_recs = db.query(Recommendation).join(
        subq,
        (Recommendation.product_id == subq.c.product_id) &
        (Recommendation.created_at == subq.c.max_created)
    ).filter(
        Recommendation.shop_id == shop_id,
        Recommendation.is_demo == is_demo,
        Recommendation.applied_at.is_(None)
    ).all()
    
    # ✅ UNIQUE Produkte mit Empfehlungen (sollte jetzt = len(pending_recs) sein)
    unique_product_ids = set(rec.product_id for rec in pending_recs)
    
    applied_recs = db.query(Recommendation).filter(
        Recommendation.shop_id == shop_id,
        Recommendation.is_demo == is_demo,
        Recommendation.applied_at.isnot(None)  # APPLIED
    ).count()
    
    # ============================================
    # 2. MISSED REVENUE BERECHNUNG
    # ============================================
    total_missed = 0
    
    for rec in pending_recs:
        price_diff = rec.recommended_price - rec.current_price
        
        # Nutze sales_30d wenn vorhanden
        if rec.sales_30d and rec.sales_30d > 0:
            # Hochrechnen auf Monat (sales_30d ist bereits für 30 Tage)
            monthly_potential = rec.sales_30d * price_diff
        elif rec.sales_7d and rec.sales_7d > 0:
            # Hochrechnen auf Monat (sales_7d * 30/7)
            monthly_potential = (rec.sales_7d / 7 * 30) * price_diff
        else:
            # Fallback: Schätze 5 Verkäufe/Monat
            monthly_potential = 5 * price_diff
        
        total_missed += monthly_potential
    
    # ✅ FIXED: Separate Zählung für Produkte vs. Empfehlungen
    missed_revenue = {
        "total": round(total_missed, 2),
        "product_count": len(unique_product_ids),  # ✅ Unique Produkte (z.B. 15)
        "recommendation_count": len(pending_recs),  # ✅ Alle Recs (z.B. 166)
        "avg_per_product": round(total_missed / len(unique_product_ids), 2) if unique_product_ids else 0
    }
    
    # ============================================
    # 3. TRUST LADDER
    # ============================================
    points = 0
    completed_steps = []
    pending_steps = []
    
    # +10 Punkte: Shop hat Produkte
    if products_count > 0:
        points += 10
        completed_steps.append(f"✅ {products_count} Produkte synchronisiert")
    else:
        pending_steps.append({
            "text": "Produkte synchronisieren",
            "points": 10,
            "action": "products"
        })
    
    # +5 Punkte: Empfehlungen erstellt
    total_recs = len(pending_recs) + applied_recs
    if total_recs > 0:
        points += 5
        completed_steps.append(f"✅ {total_recs} Preisempfehlungen erstellt")
    else:
        pending_steps.append({
            "text": "Erste Preisempfehlung erstellen",
            "points": 5,
            "action": "recommendations"
        })
    
    # +15 Punkte: Erste Empfehlung angewendet
    if applied_recs > 0:
        points += 15
        completed_steps.append(f"✅ {applied_recs} Empfehlungen umgesetzt")
    else:
        pending_steps.append({
            "text": "Erste Empfehlung anwenden",
            "points": 15,
            "action": "recommendations"
        })
    
    # +10 Punkte: Kosten für min. 5 Produkte
    products_with_costs = db.query(Product).filter(
        Product.shop_id == shop_id,
        Product.cost.isnot(None)
    ).count()
    
    if products_with_costs >= 5:
        points += 10
        completed_steps.append(f"✅ Kosten für {products_with_costs} Produkte hinterlegt")
    else:
        needed = 5 - products_with_costs
        pending_steps.append({
            "text": f"Kosten für {needed} weitere Produkte hinterlegen (aktuell: {products_with_costs}/5)",
            "points": 10,
            "action": "products"
        })
    
    # +20 Punkte: 10+ angewendet
    if applied_recs >= 10:
        points += 20
        completed_steps.append(f"🎉 {applied_recs} Empfehlungen erfolgreich umgesetzt!")
    else:
        needed = 10 - applied_recs
        if needed > 0:
            pending_steps.append({
                "text": f"{needed} weitere Empfehlungen anwenden (aktuell: {applied_recs}/10)",
                "points": 20,
                "action": "recommendations"
            })
    
    # Level bestimmen
    if points < 20:
        level, next_level = "bronze", 20
    elif points < 50:
        level, next_level = "silver", 50
    elif points < 100:
        level, next_level = "gold", 100
    else:
        level, next_level = "platinum", 150
    
    # Berechne fehlende Punkte bis zum nächsten Level
    points_needed = next_level - points
    
    # Filtere pending_steps: Zeige nur die, die zum nächsten Level führen
    # Sortiere nach Punkten (höchste zuerst) und zeige max. 3
    relevant_pending_steps = sorted(
        [step for step in pending_steps if step["points"] <= points_needed],
        key=lambda x: x["points"],
        reverse=True
    )[:3]
    
    # Falls keine relevanten Steps, zeige die nächsten verfügbaren
    if not relevant_pending_steps and pending_steps:
        relevant_pending_steps = sorted(pending_steps, key=lambda x: x["points"], reverse=True)[:3]
    
    progress = {
        "level": level,
        "points": points,
        "next_level_points": next_level,
        "points_needed": points_needed,
        "completed_steps": completed_steps,
        "pending_steps": relevant_pending_steps
    }
    
    # ============================================
    # 4. NEXT STEPS
    # ============================================
    next_steps = []
    
    # Dringend: Pending Empfehlungen
    if len(unique_product_ids) > 0:
        next_steps.append({
            "urgent": True,
            "title": f"🔥 {len(unique_product_ids)} {'Produkt braucht' if len(unique_product_ids) == 1 else 'Produkte brauchen'} Optimierung!",
            "description": f"{len(pending_recs)} Preisempfehlungen warten darauf, umgesetzt zu werden. Potenzial: bis zu {round(total_missed):,} € mehr Umsatz.",
            "action": "Produkte ansehen",  # ✅ FIXED: "Produkte" statt "Empfehlungen"
            "href": "/products"  # ✅ FIXED: zu /products
        })
    
    # Keine Produkte
    if products_count == 0:
        next_steps.append({
            "urgent": True,
            "title": "Keine Produkte gefunden",
            "description": "Synchronisiere deine Shopify-Produkte.",
            "action": "Produkte synchronisieren",
            "href": "/products"
        })
    
    # Fehlende Kosten
    if products_with_costs < products_count * 0.5 and products_count > 0:
        next_steps.append({
            "urgent": False,
            "title": "Kosten-Daten vervollständigen",
            "description": f"Hinterlege Kosten für mehr Produkte (aktuell: {products_with_costs}/{products_count})",
            "action": "Kosten hinzufügen",
            "href": "/products"
        })
    
    return {
        "products_count": products_count,  # ✅ 20 (alle Produkte)
        "recommendations_pending": len(pending_recs),  # ✅ 166 (alle Recommendations)
        "products_with_recommendations": len(unique_product_ids),  # ✅ 15 (Produkte mit Recs)
        "recommendations_applied": applied_recs,
        "missed_revenue": missed_revenue,
        "progress": progress,
        "next_steps": next_steps
    }

