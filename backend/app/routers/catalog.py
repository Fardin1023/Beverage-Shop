import io
from fastapi import APIRouter, HTTPException, Path, UploadFile, File, Form, Response
from pydantic import BaseModel
from typing import Optional, List
from app.db import get_db
from app.pdf_utils import parse_products_pdf, generate_sample_pdf_bytes, CATEGORY_ICONS

router = APIRouter(prefix="/api/catalog", tags=["Catalog Management"])

class MenuItemCreate(BaseModel):
    name: str
    category: str  # 'Pepsi', '7up', 'Miranda Orange', 'Mountain Dew', 'Sting', 'Slice', 'Aquafina Water', 'Carbonated Drinks'
    description: Optional[str] = ""
    price: float
    available_day_of_week: Optional[int] = None  # 1=Sun..7=Sat
    image_url: Optional[str] = "🥤"

class ManualProductCreate(BaseModel):
    name: str
    category: str
    price: float
    description: Optional[str] = ""
    available_day_of_week: Optional[int] = None
    image_url: Optional[str] = None
    auto_create_inventory: bool = True
    opening_stock: float = 25.0
    ingredient_unit: str = "bottles"


class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    available_day_of_week: Optional[int] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None

class InventoryItemCreate(BaseModel):
    name: str
    unit: str  # 'kg', 'L', 'g', 'units'
    low_stock_threshold: float = 10.0
    critical_stock_threshold: float = 5.0
    initial_opening_stock: float = 20.0

class RecipeIngredientInput(BaseModel):
    menu_item_id: int
    inventory_item_id: int
    quantity_required: float

class StockResetInput(BaseModel):
    inventory_item_id: int
    new_quantity: float

@router.get("/products")
def get_catalog_products():
    """List all menu items currently in the catalog"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    id, name, category, description,
                    CAST(price AS FLOAT) AS price,
                    available_day_of_week, image_url, is_active,
                    created_at
                FROM menu_items
                ORDER BY is_active DESC, category ASC, name ASC;
            """)
            items = cur.fetchall()
            return {"count": len(items), "products": items}

@router.post("/manual-product")
def add_manual_product(payload: ManualProductCreate):
    """
    Option 1: Manually add a product through typed form inputs.
    Optionally auto-creates an associated inventory ingredient and initializes opening stock.
    """
    clean_name = payload.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Product name is required.")
    if payload.price <= 0:
        raise HTTPException(status_code=400, detail="Price must be greater than zero.")

    icon = payload.image_url or CATEGORY_ICONS.get(payload.category, '🥤')

    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                conn.begin()

                # 1. Insert into menu_items
                cur.execute("""
                    INSERT INTO menu_items (name, category, description, price, available_day_of_week, image_url, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, 1)
                """, (clean_name, payload.category, payload.description or f"Chilled {clean_name}", payload.price, payload.available_day_of_week, icon))
                menu_id = cur.lastrowid

                # 2. If auto_create_inventory is True, add to inventory_items and shop_stock
                inv_id = None
                if payload.auto_create_inventory:
                    ingredient_name = clean_name
                    cur.execute("SELECT id FROM inventory_items WHERE name = %s", (ingredient_name,))
                    existing_inv = cur.fetchone()
                    if existing_inv:
                        inv_id = existing_inv['id']
                    else:
                        cur.execute("""
                            INSERT INTO inventory_items (name, unit, low_stock_threshold, critical_stock_threshold)
                            VALUES (%s, %s, 10.0, 3.0)
                        """, (ingredient_name, payload.ingredient_unit or "bottles"))
                        inv_id = cur.lastrowid


                    # Create stock entry
                    cur.execute("""
                        INSERT INTO shop_stock (inventory_item_id, current_quantity, last_updated_by)
                        VALUES (%s, %s, 2)
                        ON DUPLICATE KEY UPDATE current_quantity = %s
                    """, (inv_id, payload.opening_stock, payload.opening_stock))

                    # Link BOM recipe
                    cur.execute("""
                        INSERT INTO recipe_ingredients (menu_item_id, inventory_item_id, quantity_required)
                        VALUES (%s, %s, 1.0)
                        ON DUPLICATE KEY UPDATE quantity_required = 1.0
                    """, (menu_id, inv_id))

                conn.commit()
                return {
                    "success": True,
                    "menu_item_id": menu_id,
                    "name": clean_name,
                    "price": payload.price,
                    "category": payload.category,
                    "inventory_item_id": inv_id,
                    "message": f"Successfully added '{clean_name}' (${payload.price:.2f}) to catalog!"
                }
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=f"Failed to add manual product: {str(e)}")

@router.post("/upload-pdf")
async def upload_products_pdf(
    file: UploadFile = File(...),
    auto_create_inventory: bool = Form(True),
    opening_stock: float = Form(20.0)
):
    """
    Option 2: Batch import products from an uploaded PDF products list.
    Extracts text using pypdf, parses drinks, prices, categories, and inserts into database.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a PDF file (.pdf).")

    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")

        parsed_items = parse_products_pdf(content)
        if not parsed_items:
            raise HTTPException(
                status_code=400,
                detail="Could not detect beverage products in the uploaded PDF. Please ensure the PDF lists drink names, categories, and prices (e.g., 'Latte | Coffee | $4.50 | Description')."
            )

        imported = []
        with get_db() as conn:
            try:
                with conn.cursor() as cur:
                    conn.begin()
                    for item in parsed_items:
                        # 1. Insert or update menu_item
                        cur.execute("""
                            INSERT INTO menu_items (name, category, description, price, available_day_of_week, image_url, is_active)
                            VALUES (%s, %s, %s, %s, %s, %s, 1)
                        """, (
                            item['name'],
                            item['category'],
                            item['description'],
                            item['price'],
                            item['available_day_of_week'],
                            item['image_url']
                        ))
                        menu_id = cur.lastrowid

                        # 2. Auto-create inventory & stock if enabled
                        if auto_create_inventory:
                            ing_name = item['name']
                            cur.execute("SELECT id FROM inventory_items WHERE name = %s", (ing_name,))
                            existing = cur.fetchone()
                            if existing:
                                inv_id = existing['id']
                            else:
                                cur.execute("""
                                    INSERT INTO inventory_items (name, unit, low_stock_threshold, critical_stock_threshold)
                                    VALUES (%s, 'bottles', 10.0, 3.0)
                                """, (ing_name,))
                                inv_id = cur.lastrowid

                            cur.execute("""
                                INSERT INTO shop_stock (inventory_item_id, current_quantity, last_updated_by)

                                VALUES (%s, %s, 2)
                                ON DUPLICATE KEY UPDATE current_quantity = %s
                            """, (inv_id, opening_stock, opening_stock))

                            cur.execute("""
                                INSERT INTO recipe_ingredients (menu_item_id, inventory_item_id, quantity_required)
                                VALUES (%s, %s, 1.0)
                                ON DUPLICATE KEY UPDATE quantity_required = 1.0
                            """, (menu_id, inv_id))

                        imported.append({
                            "id": menu_id,
                            "name": item['name'],
                            "category": item['category'],
                            "price": item['price']
                        })

                    conn.commit()
            except Exception as e:
                conn.rollback()
                raise HTTPException(status_code=500, detail=f"Database import failed: {str(e)}")

        return {
            "success": True,
            "filename": file.filename,
            "imported_count": len(imported),
            "imported_items": imported,
            "message": f"Successfully parsed & imported {len(imported)} products from '{file.filename}'!"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF parsing error: {str(e)}")

@router.post("/clear-data")
def clear_all_data():
    """
    Remove all seed/operational data from the database so the user can start completely fresh.
    """
    tables = [
        'order_items',
        'orders',
        'recipe_ingredients',
        'shop_restock_request_items',
        'shop_restock_requests',
        'supplier_shop_deliveries',
        'supplier_company_orders',
        'shop_stock',
        'menu_items',
        'inventory_items',
        'customers'
    ]
    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                conn.begin()
                cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
                for tbl in tables:
                    cur.execute(f"DELETE FROM `{tbl}`;")
                cur.execute("SET FOREIGN_KEY_CHECKS = 1;")
                conn.commit()
                return {"success": True, "message": "All database seed data removed. Ready for manual entry!"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to clear data: {str(e)}")

@router.get("/sample-pdf")
def download_sample_pdf():
    """
    Download a sample Products List PDF ready for testing the PDF parser.
    """
    pdf_bytes = generate_sample_pdf_bytes()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=sample_products_list.pdf"}
    )

@router.post("/menu-item")
def create_menu_item(payload: MenuItemCreate):
    """Add a new custom drink or secret drop to the catalog"""
    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                conn.begin()
                cur.execute("""
                    INSERT INTO menu_items (name, category, description, price, available_day_of_week, image_url, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, 1)
                """, (payload.name, payload.category, payload.description, payload.price, payload.available_day_of_week, payload.image_url))
                new_id = cur.lastrowid
                conn.commit()
                return {"success": True, "menu_item_id": new_id, "message": f"Created drink '{payload.name}' (${payload.price:.2f})"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))

@router.patch("/menu-item/{item_id}")
def update_menu_item(item_id: int, payload: MenuItemUpdate):
    """Update pricing, availability or details for a menu item"""
    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                conn.begin()
                fields = []
                values = []
                if payload.name is not None:
                    fields.append("name = %s")
                    values.append(payload.name)
                if payload.category is not None:
                    fields.append("category = %s")
                    values.append(payload.category)
                if payload.description is not None:
                    fields.append("description = %s")
                    values.append(payload.description)
                if payload.price is not None:
                    fields.append("price = %s")
                    values.append(payload.price)
                if payload.available_day_of_week is not None:
                    fields.append("available_day_of_week = %s")
                    values.append(payload.available_day_of_week)
                if payload.image_url is not None:
                    fields.append("image_url = %s")
                    values.append(payload.image_url)
                if payload.is_active is not None:
                    fields.append("is_active = %s")
                    values.append(1 if payload.is_active else 0)

                if not fields:
                    raise HTTPException(status_code=400, detail="No fields to update")

                values.append(item_id)
                cur.execute(f"UPDATE menu_items SET {', '.join(fields)} WHERE id = %s", values)
                conn.commit()
                return {"success": True, "message": f"Updated menu item #{item_id}"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))

@router.delete("/menu-item/{item_id}")
def delete_menu_item(item_id: int):
    """Deactivate or remove a menu item"""
    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                conn.begin()
                cur.execute("DELETE FROM menu_items WHERE id = %s", (item_id,))
                conn.commit()
                return {"success": True, "message": f"Deleted menu item #{item_id}"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))

@router.post("/inventory-item")
def create_inventory_item(payload: InventoryItemCreate):
    """Add a new raw ingredient and set its initial opening stock in shop_stock"""
    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                conn.begin()
                cur.execute("""
                    INSERT INTO inventory_items (name, unit, low_stock_threshold, critical_stock_threshold)
                    VALUES (%s, %s, %s, %s)
                """, (payload.name, payload.unit, payload.low_stock_threshold, payload.critical_stock_threshold))
                inv_id = cur.lastrowid

                # Initialize opening stock in shop_stock
                cur.execute("""
                    INSERT INTO shop_stock (inventory_item_id, current_quantity, last_updated_by)
                    VALUES (%s, %s, 1)
                    ON DUPLICATE KEY UPDATE current_quantity = %s
                """, (inv_id, payload.initial_opening_stock, payload.initial_opening_stock))

                conn.commit()
                return {
                    "success": True,
                    "inventory_item_id": inv_id,
                    "opening_stock": payload.initial_opening_stock,
                    "unit": payload.unit,
                    "message": f"Created ingredient '{payload.name}' with opening stock of {payload.initial_opening_stock} {payload.unit}"
                }
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))

@router.post("/recipe-ingredient")
def link_recipe_ingredient(payload: RecipeIngredientInput):
    """Link a menu item to an inventory ingredient with depletion ratio (BOM)"""
    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                conn.begin()
                cur.execute("""
                    INSERT INTO recipe_ingredients (menu_item_id, inventory_item_id, quantity_required)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE quantity_required = %s
                """, (payload.menu_item_id, payload.inventory_item_id, payload.quantity_required, payload.quantity_required))
                conn.commit()
                return {"success": True, "message": "Recipe BOM ingredient saved!"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))

@router.post("/set-stock")
def set_stock(payload: StockResetInput):
    """Directly override / set opening stock balance for any ingredient"""
    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                conn.begin()
                cur.execute("""
                    UPDATE shop_stock
                    SET current_quantity = %s, last_updated_by = 1
                    WHERE inventory_item_id = %s
                """, (payload.new_quantity, payload.inventory_item_id))
                conn.commit()
                return {"success": True, "message": f"Updated stock to {payload.new_quantity}"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))
