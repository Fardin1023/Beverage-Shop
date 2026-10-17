from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import random
import string
from app.db import get_db

router = APIRouter(prefix="/api", tags=["Customer"])

class OrderItemInput(BaseModel):
    menu_item_id: int
    quantity: int = 1

class PlaceOrderInput(BaseModel):
    phone: Optional[str] = None
    items: List[OrderItemInput]

def generate_pickup_token() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choices(chars, k=4))
    return f"TK-{suffix}"

@router.get("/customer/lookup")
def customer_lookup(phone: str = Query(..., description="Customer phone number")):
    clean_phone = phone.strip()
    with get_db() as conn:
        with conn.cursor() as cur:
            # 1. Fetch customer details
            cur.execute("""
                SELECT id, phone, full_name, punch_card_stamps, rewards_earned, created_at
                FROM customers
                WHERE phone = %s LIMIT 1
            """, (clean_phone,))
            customer = cur.fetchone()

            if not customer:
                # Return friendly default for new customer
                return {
                    "found": False,
                    "phone": clean_phone,
                    "full_name": "New Drinker",
                    "punch_card_stamps": 0,
                    "rewards_earned": 0,
                    "stamps_needed_for_reward": 6,
                    "most_ordered_drink": None
                }

            # 2. Compute most ordered drink via aggregated SQL
            cur.execute("""
                SELECT mi.name, mi.image_url, SUM(oi.quantity) AS total_ordered
                FROM orders o
                JOIN order_items oi ON o.id = oi.order_id
                JOIN menu_items mi ON oi.menu_item_id = mi.id
                WHERE o.customer_id = %s
                GROUP BY mi.id, mi.name, mi.image_url
                ORDER BY total_ordered DESC
                LIMIT 1
            """, (customer['id'],))
            favorite = cur.fetchone()

            return {
                "found": True,
                "customer_id": customer['id'],
                "phone": customer['phone'],
                "full_name": customer['full_name'],
                "punch_card_stamps": customer['punch_card_stamps'],
                "rewards_earned": customer['rewards_earned'],
                "stamps_needed_for_reward": max(0, 6 - customer['punch_card_stamps']),
                "most_ordered_drink": favorite['name'] if favorite else None,
                "most_ordered_icon": favorite['image_url'] if favorite else None
            }

import time

@router.get("/menu/exclusive-drop")
def get_exclusive_drop(force_random: bool = False):
    """
    Returns an exclusive drink that changes randomly every 10 minutes (600 seconds).
    All clients are synchronized to the 10-minute clock interval (00, 10, 20, 30, 40, 50 mins of each hour).
    """
    now = time.time()
    interval_seconds = 600
    window_id = int(now // interval_seconds)
    seconds_remaining = int(interval_seconds - (now % interval_seconds))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    id, name, category, description, 
                    CAST(price AS FLOAT) AS price, 
                    image_url, 1 AS is_secret_drop
                FROM menu_items
                WHERE category = 'Secret Drop' AND is_active = 1
                ORDER BY id ASC;
            """)
            secret_pool = cur.fetchall()

            if not secret_pool:
                return {
                    "has_exclusive": False,
                    "window_id": window_id,
                    "seconds_remaining": seconds_remaining,
                    "exclusive_item": None
                }

            if force_random:
                selected_item = random.choice(secret_pool)
            else:
                rng = random.Random(window_id)
                selected_item = rng.choice(secret_pool)

            return {
                "has_exclusive": True,
                "window_id": window_id,
                "interval_seconds": interval_seconds,
                "seconds_remaining": seconds_remaining,
                "exclusive_item": selected_item
            }

@router.get("/menu/daily")
def daily_menu():
    """Fetch standard menu items plus the active 10-minute Exclusive Secret Drop"""
    with get_db() as conn:
        with conn.cursor() as cur:
            # 1. Fetch standard menu items
            cur.execute("""
                SELECT 
                    id, 
                    name, 
                    category, 
                    description, 
                    CAST(price AS FLOAT) AS price, 
                    available_day_of_week, 
                    image_url,
                    (category = 'Secret Drop' OR available_day_of_week IS NOT NULL) AS is_secret_drop,
                    DAYNAME(CURDATE()) AS today_name,
                    DAYOFWEEK(CURDATE()) AS today_day_of_week
                FROM menu_items
                WHERE is_active = 1
                  AND (category <> 'Secret Drop')
                ORDER BY 
                    category ASC,
                    id ASC
            """)
            items = cur.fetchall()

            # 2. Get the active 10-minute random exclusive drop
            exclusive_res = get_exclusive_drop(force_random=False)
            active_exclusive = exclusive_res.get("exclusive_item")
            if active_exclusive:
                active_exclusive['is_secret_drop'] = True
                active_exclusive['available_day_of_week'] = None
                items.insert(0, active_exclusive)

            cur.execute("SELECT DAYNAME(CURDATE()) AS day_name, DAYOFWEEK(CURDATE()) AS day_num")
            day_info = cur.fetchone()

            return {
                "day_name": day_info['day_name'] if day_info else 'Today',
                "day_of_week": day_info['day_num'] if day_info else 1,
                "items": items,
                "exclusive_drop": active_exclusive,
                "seconds_remaining": exclusive_res.get("seconds_remaining", 600)
            }

@router.post("/orders/place")
def place_order(payload: PlaceOrderInput):
    """
    Open transaction.
    Insert row into orders and generate a short alphanumeric pickup_token.
    Insert line items into order_items.
    Decrement raw ingredients from shop_stock matching the BOM recipe.
    Increment customer punch card stamps.
    Commit transaction.
    """
    if not payload.items:
        raise HTTPException(status_code=400, detail="Order must contain at least one item.")

    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                conn.begin()

                # 1. Handle Customer Loyalty
                customer_id = None
                new_stamps = 0
                new_rewards = 0
                if payload.phone and payload.phone.strip():
                    phone_clean = payload.phone.strip()
                    cur.execute("SELECT id, punch_card_stamps, rewards_earned FROM customers WHERE phone = %s FOR UPDATE", (phone_clean,))
                    cust = cur.fetchone()

                    if not cust:
                        # Auto register customer with 1 stamp
                        cur.execute("""
                            INSERT INTO customers (phone, full_name, punch_card_stamps, rewards_earned)
                            VALUES (%s, 'Daily Regular', 1, 0)
                        """, (phone_clean,))
                        customer_id = cur.lastrowid
                        new_stamps = 1
                        new_rewards = 0
                    else:
                        customer_id = cust['id']
                        stamps = cust['punch_card_stamps'] + 1
                        rewards = cust['rewards_earned']
                        if stamps >= 6:
                            rewards += 1
                            stamps = 0
                        cur.execute("""
                            UPDATE customers
                            SET punch_card_stamps = %s, rewards_earned = %s
                            WHERE id = %s
                        """, (stamps, rewards, customer_id))
                        new_stamps = stamps
                        new_rewards = rewards

                # 2. Calculate totals and check menu items
                total_amount = 0.0
                order_items_data = []

                for item in payload.items:
                    cur.execute("SELECT id, name, price FROM menu_items WHERE id = %s AND is_active = 1", (item.menu_item_id,))
                    menu_row = cur.fetchone()
                    if not menu_row:
                        raise HTTPException(status_code=404, detail=f"Menu item ID {item.menu_item_id} not found or inactive")
                    
                    price = float(menu_row['price'])
                    subtotal = price * item.quantity
                    total_amount += subtotal
                    order_items_data.append({
                        "menu_item_id": item.menu_item_id,
                        "name": menu_row['name'],
                        "quantity": item.quantity,
                        "unit_price": price,
                        "subtotal": subtotal
                    })

                # 3. Generate unique pickup token and insert into orders
                pickup_token = generate_pickup_token()
                cur.execute("""
                    INSERT INTO orders (customer_id, pickup_token, total_amount, status)
                    VALUES (%s, %s, %s, 'completed')
                """, (customer_id, pickup_token, total_amount))
                order_id = cur.lastrowid

                # 4. Insert order_items and decrement raw ingredients from shop_stock
                for oi in order_items_data:
                    cur.execute("""
                        INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, subtotal)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (order_id, oi['menu_item_id'], oi['quantity'], oi['unit_price'], oi['subtotal']))

                    # BOM Depletion: Decrement raw ingredients matching recipe_ingredients
                    cur.execute("""
                        UPDATE shop_stock ss
                        JOIN recipe_ingredients ri ON ss.inventory_item_id = ri.inventory_item_id
                        SET ss.current_quantity = GREATEST(0, ss.current_quantity - (ri.quantity_required * %s))
                        WHERE ri.menu_item_id = %s
                    """, (oi['quantity'], oi['menu_item_id']))

                conn.commit()

                return {
                    "success": True,
                    "order_id": order_id,
                    "pickup_token": pickup_token,
                    "total_amount": round(total_amount, 2),
                    "items_count": sum(i['quantity'] for i in order_items_data),
                    "punch_card_stamps": new_stamps,
                    "rewards_earned": new_rewards,
                    "message": f"Order #{order_id} placed successfully! Pickup Token: {pickup_token}"
                }
        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")
