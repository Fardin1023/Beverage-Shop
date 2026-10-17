from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.db import get_db

router = APIRouter(prefix="/api/shop", tags=["Shopkeeper"])

class StockAdjustInput(BaseModel):
    inventory_item_id: int
    delta: float  # e.g., +1.00 or -1.00
    user_id: Optional[int] = 1

class RestockRequestInput(BaseModel):
    inventory_item_ids: List[int]
    user_id: Optional[int] = 1
    notes: Optional[str] = "Manual counter restock alert"

@router.get("/stock")
def get_shop_stock():
    """
    Return all current inventory items, current quantity, unit,
    and calculated status flag (OK_GREEN, LOW_YELLOW, CRITICAL_RED).
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    ii.id AS inventory_item_id,
                    ii.name,
                    ii.unit,
                    CAST(ss.current_quantity AS FLOAT) AS current_quantity,
                    CAST(ii.low_stock_threshold AS FLOAT) AS low_stock_threshold,
                    CAST(ii.critical_stock_threshold AS FLOAT) AS critical_stock_threshold,
                    ss.updated_at,
                    u.full_name AS last_updated_by_name,
                    CASE 
                        WHEN ss.current_quantity <= ii.critical_stock_threshold THEN 'CRITICAL_RED'
                        WHEN ss.current_quantity <= ii.low_stock_threshold THEN 'LOW_YELLOW'
                        ELSE 'OK_GREEN'
                    END AS calculated_status_flag
                FROM inventory_items ii
                JOIN shop_stock ss ON ii.id = ss.inventory_item_id
                LEFT JOIN users u ON ss.last_updated_by = u.id
                ORDER BY 
                    CASE 
                        WHEN ss.current_quantity <= ii.critical_stock_threshold THEN 1
                        WHEN ss.current_quantity <= ii.low_stock_threshold THEN 2
                        ELSE 3
                    END,
                    ii.id ASC
            """)
            stocks = cur.fetchall()
            return {"count": len(stocks), "stock": stocks}

@router.patch("/stock/adjust")
def adjust_stock(payload: StockAdjustInput):
    """
    Inputs: inventory_item_id, delta (must be negative for waste/spoilage), user_id.
    Note: Product quantities can only be added to the database through the supplier.
    """
    if payload.delta > 0:
        raise HTTPException(
            status_code=403, 
            detail="Permission Denied: Products quantity can only be added in the database through the supplier only."
        )

    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                conn.begin()
                # Check item exists
                cur.execute("SELECT id FROM inventory_items WHERE id = %s", (payload.inventory_item_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Inventory item not found")

                # Atomic update with GREATEST to prevent negative inventory
                cur.execute("""
                    UPDATE shop_stock
                    SET current_quantity = GREATEST(0.00, current_quantity + %s),
                        last_updated_by = %s
                    WHERE inventory_item_id = %s
                """, (payload.delta, payload.user_id, payload.inventory_item_id))

                # Fetch updated status
                cur.execute("""
                    SELECT 
                        ii.id AS inventory_item_id,
                        ii.name,
                        ii.unit,
                        CAST(ss.current_quantity AS FLOAT) AS current_quantity,
                        CAST(ii.low_stock_threshold AS FLOAT) AS low_stock_threshold,
                        CAST(ii.critical_stock_threshold AS FLOAT) AS critical_stock_threshold,
                        CASE 
                            WHEN ss.current_quantity <= ii.critical_stock_threshold THEN 'CRITICAL_RED'
                            WHEN ss.current_quantity <= ii.low_stock_threshold THEN 'LOW_YELLOW'
                            ELSE 'OK_GREEN'
                        END AS calculated_status_flag
                    FROM inventory_items ii
                    JOIN shop_stock ss ON ii.id = ss.inventory_item_id
                    WHERE ii.id = %s
                """, (payload.inventory_item_id,))
                updated_item = cur.fetchone()

                conn.commit()
                return {
                    "success": True,
                    "message": f"Updated {updated_item['name']} by {payload.delta:+.2f} {updated_item['unit']}",
                    "item": updated_item
                }
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Stock adjustment failed: {str(e)}")

@router.post("/restock-request")
def create_restock_request(payload: RestockRequestInput):
    """
    Trigger manual restock ping to the assigned supplier for one or more critical items.
    """
    if not payload.inventory_item_ids:
        raise HTTPException(status_code=400, detail="Must select at least one item to request restock.")

    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                conn.begin()
                # Create main restock request
                cur.execute("""
                    INSERT INTO shop_restock_requests (requested_by, status, notes)
                    VALUES (%s, 'pending', %s)
                """, (payload.user_id, payload.notes))
                request_id = cur.lastrowid

                # Insert requested items
                requested_details = []
                for item_id in payload.inventory_item_ids:
                    cur.execute("""
                        SELECT ii.name, ii.low_stock_threshold, ii.unit
                        FROM inventory_items ii
                        WHERE ii.id = %s
                    """, (item_id,))
                    item_meta = cur.fetchone()
                    if not item_meta:
                        continue
                    
                    # Default suggested batch: 2x low stock threshold
                    suggested_qty = float(item_meta['low_stock_threshold']) * 2.0
                    cur.execute("""
                        INSERT INTO shop_restock_request_items (request_id, inventory_item_id, requested_quantity, status)
                        VALUES (%s, %s, %s, 'pending')
                    """, (request_id, item_id, suggested_qty))
                    
                    requested_details.append({
                        "inventory_item_id": item_id,
                        "name": item_meta['name'],
                        "suggested_quantity": suggested_qty,
                        "unit": item_meta['unit']
                    })

                conn.commit()
                return {
                    "success": True,
                    "request_id": request_id,
                    "items": requested_details,
                    "message": f"Restock ping successfully dispatched to supplier for {len(requested_details)} items!"
                }
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to create restock request: {str(e)}")


@router.get("/sales-demand")
def get_sales_demand():
    """
    Return product demand based on sales numbers, including:
    1. Units sold & revenue per menu item.
    2. Summary totals (total orders, total drinks sold, total revenue).
    3. Ingredient consumption demand derived from BOM recipe.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            # Aggregate sales by product
            cur.execute("""
                SELECT 
                    mi.id AS menu_item_id,
                    mi.name AS item_name,
                    mi.category,
                    CAST(mi.price AS FLOAT) AS unit_price,
                    mi.image_url,
                    COALESCE(SUM(oi.quantity), 0) AS total_units_sold,
                    CAST(COALESCE(SUM(oi.subtotal), 0.0) AS FLOAT) AS total_revenue,
                    COUNT(DISTINCT oi.order_id) AS distinct_orders_count
                FROM menu_items mi
                LEFT JOIN order_items oi ON mi.id = oi.menu_item_id
                LEFT JOIN orders o ON oi.order_id = o.id AND o.status = 'completed'
                WHERE mi.is_active = 1
                GROUP BY mi.id, mi.name, mi.category, mi.price, mi.image_url
                ORDER BY total_units_sold DESC, total_revenue DESC, mi.name ASC
            """)
            demand_items = cur.fetchall()

            # Overall summary metrics
            cur.execute("""
                SELECT 
                    COUNT(id) AS total_completed_orders,
                    CAST(COALESCE(SUM(total_amount), 0.0) AS FLOAT) AS total_sales_revenue
                FROM orders
                WHERE status = 'completed'
            """)
            orders_summary = cur.fetchone()

            total_units = sum(int(item['total_units_sold']) for item in demand_items)
            top_product = demand_items[0]['item_name'] if demand_items and demand_items[0]['total_units_sold'] > 0 else "None yet"

            # Ingredient consumption demand derived from BOM recipe
            cur.execute("""
                SELECT 
                    ii.id AS inventory_item_id,
                    ii.name AS ingredient_name,
                    ii.unit,
                    CAST(ss.current_quantity AS FLOAT) AS current_stock,
                    CAST(COALESCE(SUM(ri.quantity_required * oi.quantity), 0.0) AS FLOAT) AS total_depleted_demand
                FROM inventory_items ii
                JOIN shop_stock ss ON ii.id = ss.inventory_item_id
                LEFT JOIN recipe_ingredients ri ON ii.id = ri.inventory_item_id
                LEFT JOIN order_items oi ON ri.menu_item_id = oi.menu_item_id
                LEFT JOIN orders o ON oi.order_id = o.id AND o.status = 'completed'
                GROUP BY ii.id, ii.name, ii.unit, ss.current_quantity
                ORDER BY total_depleted_demand DESC
            """)
            ingredient_demand = cur.fetchall()

            return {
                "summary": {
                    "total_completed_orders": orders_summary['total_completed_orders'] if orders_summary else 0,
                    "total_sales_revenue": orders_summary['total_sales_revenue'] if orders_summary else 0.0,
                    "total_units_sold": total_units,
                    "top_demanded_product": top_product
                },
                "products_demand": demand_items,
                "ingredients_demand": ingredient_demand
            }

