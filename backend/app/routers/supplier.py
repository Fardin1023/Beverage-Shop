from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
from app.db import get_db

router = APIRouter(prefix="/api/supplier", tags=["Supplier"])

class DeliveryInput(BaseModel):
    restock_request_id: Optional[int] = None
    inventory_item_id: int
    supplier_user_id: Optional[int] = 2  # Default to Bob Martinez
    delivery_date: Optional[str] = None   # Defaults to CURDATE()
    challan_number: str
    unit_cost: float = 0.00
    quantity: float

class CompanyOrderInput(BaseModel):
    supplier_user_id: Optional[int] = 2
    inventory_item_id: int
    requested_quantity: float
    requisition_notes: Optional[str] = "Bulk distributor restock requisition"

@router.get("/items")
def get_inventory_items():
    """List catalog items for supplier dropdown selector"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, unit, low_stock_threshold FROM inventory_items ORDER BY name ASC")
            return {"items": cur.fetchall()}

@router.get("/requests")
def get_pending_restock_requests():
    """List pending restock requests submitted by the shop"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    r.id AS request_id,
                    r.created_at,
                    r.status,
                    r.notes,
                    u.full_name AS requested_by_name,
                    ri.id AS request_item_id,
                    ri.inventory_item_id,
                    ii.name AS item_name,
                    ii.unit,
                    CAST(ri.requested_quantity AS FLOAT) AS requested_quantity,
                    CAST(ss.current_quantity AS FLOAT) AS current_shop_quantity
                FROM shop_restock_requests r
                JOIN shop_restock_request_items ri ON r.id = ri.request_id
                JOIN inventory_items ii ON ri.inventory_item_id = ii.id
                JOIN shop_stock ss ON ii.id = ss.inventory_item_id
                LEFT JOIN users u ON r.requested_by = u.id
                WHERE r.status = 'pending'
                ORDER BY r.created_at DESC
            """)
            requests = cur.fetchall()
            return {"count": len(requests), "requests": requests}

@router.post("/deliveries")
def create_delivery(payload: DeliveryInput):
    """
    Open transaction.
    Insert batch record into supplier_shop_deliveries (delivery date, invoice number, unit cost, quantity).
    Automatically add delivered quantity to shop_stock.
    Update request status in shop_restock_requests to fulfilled.
    Commit transaction.
    """
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Delivery quantity must be positive.")
    if not payload.challan_number.strip():
        raise HTTPException(status_code=400, detail="Invoice / Challan number is required.")

    delivery_date = payload.delivery_date or str(date.today())

    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                conn.begin()

                # 1. Insert into supplier_shop_deliveries
                cur.execute("""
                    INSERT INTO supplier_shop_deliveries (
                        restock_request_id, inventory_item_id, supplier_user_id,
                        delivery_date, challan_number, unit_cost, quantity
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    payload.restock_request_id,
                    payload.inventory_item_id,
                    payload.supplier_user_id,
                    delivery_date,
                    payload.challan_number.strip(),
                    payload.unit_cost,
                    payload.quantity
                ))
                delivery_id = cur.lastrowid

                # 2. Automatically add delivered quantity to shop_stock
                cur.execute("""
                    UPDATE shop_stock
                    SET current_quantity = current_quantity + %s,
                        last_updated_by = %s
                    WHERE inventory_item_id = %s
                """, (payload.quantity, payload.supplier_user_id, payload.inventory_item_id))

                # 3. If restock_request_id provided, mark request as fulfilled
                if payload.restock_request_id:
                    cur.execute("""
                        UPDATE shop_restock_requests
                        SET status = 'fulfilled'
                        WHERE id = %s
                    """, (payload.restock_request_id,))

                    cur.execute("""
                        UPDATE shop_restock_request_items
                        SET status = 'fulfilled'
                        WHERE request_id = %s AND inventory_item_id = %s
                    """, (payload.restock_request_id, payload.inventory_item_id))

                # Fetch updated stock balance
                cur.execute("""
                    SELECT ii.name, ii.unit, CAST(ss.current_quantity AS FLOAT) AS new_quantity
                    FROM shop_stock ss
                    JOIN inventory_items ii ON ss.inventory_item_id = ii.id
                    WHERE ss.inventory_item_id = %s
                """, (payload.inventory_item_id,))
                stock_info = cur.fetchone()

                conn.commit()
                return {
                    "success": True,
                    "delivery_id": delivery_id,
                    "challan_number": payload.challan_number,
                    "item_name": stock_info['name'] if stock_info else "",
                    "added_quantity": payload.quantity,
                    "new_shop_stock": stock_info['new_quantity'] if stock_info else 0.0,
                    "unit": stock_info['unit'] if stock_info else "",
                    "message": f"Successfully delivered {payload.quantity} {stock_info['unit'] if stock_info else ''} of {stock_info['name'] if stock_info else ''} (Challan: {payload.challan_number})!"
                }
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Delivery processing failed: {str(e)}")

@router.post("/company-orders")
def order_from_company(payload: CompanyOrderInput):
    """
    Log a requisition order for bulk stock from the central company warehouse.
    """
    if payload.requested_quantity <= 0:
        raise HTTPException(status_code=400, detail="Requisition quantity must be greater than zero.")

    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                conn.begin()
                cur.execute("""
                    INSERT INTO supplier_company_orders (
                        supplier_user_id, inventory_item_id, requested_quantity, status, requisition_notes
                    ) VALUES (%s, %s, %s, 'submitted', %s)
                """, (
                    payload.supplier_user_id,
                    payload.inventory_item_id,
                    payload.requested_quantity,
                    payload.requisition_notes
                ))
                order_id = cur.lastrowid

                cur.execute("SELECT name, unit FROM inventory_items WHERE id = %s", (payload.inventory_item_id,))
                item_info = cur.fetchone()

                conn.commit()
                return {
                    "success": True,
                    "company_order_id": order_id,
                    "status": "submitted",
                    "item_name": item_info['name'] if item_info else "",
                    "quantity": payload.requested_quantity,
                    "unit": item_info['unit'] if item_info else "",
                    "message": f"Bulk requisition #{order_id} for {payload.requested_quantity} {item_info['unit'] if item_info else ''} {item_info['name'] if item_info else ''} submitted to Central Warehouse!"
                }
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to submit company order: {str(e)}")

@router.get("/shop-stock")
def get_supplier_view_of_shop_stock():
    """
    Direct access for the supplier to inspect the shopkeeper's stock database.
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
                    CASE 
                        WHEN ss.current_quantity <= ii.critical_stock_threshold THEN 'CRITICAL_RED'
                        WHEN ss.current_quantity <= ii.low_stock_threshold THEN 'LOW_YELLOW'
                        ELSE 'OK_GREEN'
                    END AS status_flag
                FROM inventory_items ii
                JOIN shop_stock ss ON ii.id = ss.inventory_item_id
                ORDER BY 
                    CASE 
                        WHEN ss.current_quantity <= ii.critical_stock_threshold THEN 1
                        WHEN ss.current_quantity <= ii.low_stock_threshold THEN 2
                        ELSE 3
                    END,
                    ii.id ASC
            """)
            stocks = cur.fetchall()
            return {"stock": stocks}

@router.get("/company-orders")
def get_supplier_company_orders(supplier_id: Optional[int] = 2):
    """
    List requisitions made by the supplier to the company to track approval/rejection.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    sco.id,
                    sco.inventory_item_id,
                    ii.name AS item_name,
                    ii.unit,
                    CAST(sco.requested_quantity AS FLOAT) AS requested_quantity,
                    sco.status,
                    sco.requisition_notes,
                    sco.created_at,
                    sco.updated_at
                FROM supplier_company_orders sco
                JOIN inventory_items ii ON sco.inventory_item_id = ii.id
                WHERE sco.supplier_user_id = %s
                ORDER BY sco.created_at DESC
            """, (supplier_id,))
            orders = cur.fetchall()
            return {"orders": orders}

