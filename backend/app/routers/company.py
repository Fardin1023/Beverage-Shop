from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel
from typing import Literal
from app.db import get_db

router = APIRouter(prefix="/api/company", tags=["Company Admin"])

class OrderStatusUpdate(BaseModel):
    status: Literal['submitted', 'approved', 'dispatched', 'delivered', 'rejected']

@router.get("/demand-summary")
def get_demand_summary():
    """
    Aggregated query showing bulk inventory quantities requested across all active suppliers.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    ii.id AS inventory_item_id,
                    ii.name AS item_name,
                    ii.unit,
                    COALESCE(SUM(CASE WHEN sco.status IN ('submitted', 'approved') THEN sco.requested_quantity ELSE 0 END), 0) AS total_pending_demand,
                    COALESCE(SUM(CASE WHEN sco.status = 'dispatched' THEN sco.requested_quantity ELSE 0 END), 0) AS total_dispatched_demand,
                    COALESCE(SUM(CASE WHEN sco.status = 'delivered' THEN sco.requested_quantity ELSE 0 END), 0) AS total_fulfilled_demand,
                    COALESCE(SUM(CASE WHEN sco.status = 'rejected' THEN sco.requested_quantity ELSE 0 END), 0) AS total_rejected_demand,
                    COUNT(sco.id) AS total_orders_count
                FROM inventory_items ii
                LEFT JOIN supplier_company_orders sco ON ii.id = sco.inventory_item_id
                GROUP BY ii.id, ii.name, ii.unit
                ORDER BY total_pending_demand DESC, ii.name ASC
            """)
            summary = cur.fetchall()
            return {"demand_summary": summary}

@router.get("/orders")
def get_company_orders():
    """List all bulk requisition orders across suppliers"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    sco.id,
                    sco.supplier_user_id,
                    u.full_name AS supplier_name,
                    u.phone AS supplier_phone,
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
                JOIN users u ON sco.supplier_user_id = u.id
                ORDER BY 
                    CASE sco.status
                        WHEN 'submitted' THEN 1
                        WHEN 'approved' THEN 2
                        WHEN 'dispatched' THEN 3
                        WHEN 'delivered' THEN 4
                        ELSE 5
                    END,
                    sco.created_at DESC
            """)
            orders = cur.fetchall()
            return {"orders": orders}

@router.patch("/orders/{order_id}/status")
def update_order_status(order_id: int = Path(..., description="Company order ID"), payload: OrderStatusUpdate = ...):
    """
    Transition company orders from submitted -> approved (give) or rejected (not give) -> dispatched -> delivered.
    """
    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                conn.begin()
                cur.execute("SELECT id, status FROM supplier_company_orders WHERE id = %s", (order_id,))
                existing = cur.fetchone()
                if not existing:
                    raise HTTPException(status_code=404, detail="Company order not found")

                cur.execute("""
                    UPDATE supplier_company_orders
                    SET status = %s
                    WHERE id = %s
                """, (payload.status, order_id))

                conn.commit()
                return {
                    "success": True,
                    "order_id": order_id,
                    "previous_status": existing['status'],
                    "new_status": payload.status,
                    "message": f"Order #{order_id} transitioned from '{existing['status']}' to '{payload.status}'"
                }
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")

@router.get("/supplier-deliveries")
def get_supplier_deliveries():
    """
    List all supplier shop deliveries recorded in the database.
    Gives the company full visibility into the supplier's database & delivery actions.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    ssd.id,
                    ssd.delivery_date,
                    ssd.challan_number,
                    CAST(ssd.quantity AS FLOAT) AS quantity,
                    CAST(ssd.unit_cost AS FLOAT) AS unit_cost,
                    ssd.created_at,
                    ii.name AS item_name,
                    ii.unit,
                    u.full_name AS supplier_name,
                    u.phone AS supplier_phone,
                    ssd.restock_request_id
                FROM supplier_shop_deliveries ssd
                JOIN inventory_items ii ON ssd.inventory_item_id = ii.id
                LEFT JOIN users u ON ssd.supplier_user_id = u.id
                ORDER BY ssd.delivery_date DESC, ssd.id DESC
            """)
            deliveries = cur.fetchall()
            return {"deliveries": deliveries}

