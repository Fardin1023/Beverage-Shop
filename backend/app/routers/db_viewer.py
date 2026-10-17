from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from app.db import get_db

router = APIRouter(prefix="/api/db", tags=["Database Explorer"])

class QueryInput(BaseModel):
    query: str

@router.get("/tables")
def list_tables():
    """List all database tables with live row counts and storage details"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    TABLE_NAME AS table_name,
                    TABLE_ROWS AS approximate_rows,
                    DATA_LENGTH AS data_bytes,
                    CREATE_TIME AS created_at,
                    UPDATE_TIME AS updated_at
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = 'daily_drop_db'
                ORDER BY TABLE_NAME ASC;
            """)
            tables = cur.fetchall()

            # Get exact count for each table
            result = []
            for t in tables:
                tname = t['table_name']
                cur.execute(f"SELECT COUNT(*) AS cnt FROM `{tname}`")
                exact_cnt = cur.fetchone()['cnt']
                result.append({
                    "table_name": tname,
                    "exact_rows": exact_cnt,
                    "data_bytes": t['data_bytes'] or 0,
                    "updated_at": t['updated_at']
                })
            return {"database": "daily_drop_db", "tables": result}

@router.get("/table/{table_name}")
def get_table_data(
    table_name: str,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0)
):
    """Fetch columns and live rows from any table in daily_drop_db"""
    # Sanitize table_name against whitelist
    whitelist = [
        "users", "customers", "menu_items", "inventory_items",
        "recipe_ingredients", "shop_stock", "orders", "order_items",
        "shop_restock_requests", "shop_restock_request_items",
        "supplier_shop_deliveries", "supplier_company_orders"
    ]
    if table_name not in whitelist:
        raise HTTPException(status_code=400, detail="Invalid table name")

    with get_db() as conn:
        with conn.cursor() as cur:
            # 1. Fetch column definitions
            cur.execute("""
                SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY, EXTRA
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = 'daily_drop_db' AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION ASC;
            """, (table_name,))
            columns = cur.fetchall()

            # 2. Fetch total count
            cur.execute(f"SELECT COUNT(*) AS total FROM `{table_name}`")
            total = cur.fetchone()['total']

            # 3. Fetch live rows
            order_clause = "ORDER BY id DESC" if any(c['COLUMN_NAME'] == 'id' for c in columns) else ""
            cur.execute(f"SELECT * FROM `{table_name}` {order_clause} LIMIT %s OFFSET %s", (limit, offset))
            rows = cur.fetchall()

            # Convert non-serializable objects (datetime/Decimal) to string/float
            for r in rows:
                for k, v in r.items():
                    if hasattr(v, 'isoformat'):
                        r[k] = v.isoformat()
                    elif hasattr(v, '__float__') and not isinstance(v, (int, float)):
                        r[k] = float(v)

            return {
                "table_name": table_name,
                "total_rows": total,
                "limit": limit,
                "offset": offset,
                "columns": columns,
                "rows": rows
            }

def serialize_val(v):
    if v is None:
        return None
    if isinstance(v, (int, float, bool, str)):
        return v
    if hasattr(v, 'isoformat'):
        return v.isoformat()
    if hasattr(v, '__float__'):
        return float(v)
    if isinstance(v, bytes):
        try:
            return v.decode('utf-8')
        except Exception:
            return v.hex()
    return str(v)

@router.post("/query")
def run_custom_query(payload: QueryInput):
    """Execute custom SQL queries directly against MySQL"""
    sql = payload.query.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Support shorthand table name input like "menu_items" or "orders"
    known_tables = [
        "users", "customers", "menu_items", "inventory_items",
        "recipe_ingredients", "shop_stock", "orders", "order_items",
        "shop_restock_requests", "shop_restock_request_items",
        "supplier_shop_deliveries", "supplier_company_orders"
    ]
    if sql.lower() in known_tables:
        sql = f"SELECT * FROM `{sql}`"
    elif sql.lower().rstrip(';').strip() in known_tables:
        sql = f"SELECT * FROM `{sql.lower().rstrip(';').strip()}`"

    import pymysql
    with get_db() as conn:
        try:
            # Use standard Cursor to guarantee exact column-to-value index alignment even on multi-table joins
            with conn.cursor(pymysql.cursors.Cursor) as cur:
                cur.execute(sql)
                if cur.description:
                    columns = [d[0] for d in cur.description]
                    tuple_rows = cur.fetchall()
                    raw_rows = []
                    dict_rows = []
                    for trow in tuple_rows:
                        serialized_row = [serialize_val(val) for val in trow]
                        raw_rows.append(serialized_row)
                        dict_rows.append(dict(zip(columns, serialized_row)))

                    return {
                        "type": "SELECT",
                        "affected_rows": len(raw_rows),
                        "columns": columns,
                        "raw_rows": raw_rows,
                        "rows": dict_rows
                    }
                else:
                    conn.commit()
                    return {
                        "type": "MUTATION",
                        "affected_rows": cur.rowcount,
                        "last_insert_id": cur.lastrowid
                    }
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))

class RowUpdateInput(BaseModel):
    table_name: str
    primary_key_column: str
    primary_key_value: Any
    updated_fields: Dict[str, Any]

@router.post("/update-row")
def update_table_row(payload: RowUpdateInput):
    """Update specific column values for a row in MySQL"""
    whitelist = [
        "users", "customers", "menu_items", "inventory_items",
        "recipe_ingredients", "shop_stock", "orders", "order_items",
        "shop_restock_requests", "shop_restock_request_items",
        "supplier_shop_deliveries", "supplier_company_orders"
    ]
    if payload.table_name not in whitelist:
        raise HTTPException(status_code=400, detail="Table not allowed for direct editing.")

    if not payload.updated_fields:
        raise HTTPException(status_code=400, detail="No fields provided for update.")

    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                conn.begin()
                # Verify valid columns for table
                cur.execute("""
                    SELECT COLUMN_NAME
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = 'daily_drop_db' AND TABLE_NAME = %s
                """, (payload.table_name,))
                valid_cols = {c['COLUMN_NAME'] for c in cur.fetchall()}

                if payload.primary_key_column not in valid_cols:
                    raise HTTPException(status_code=400, detail="Invalid primary key column.")

                set_clauses = []
                params = []
                for col, val in payload.updated_fields.items():
                    if col in valid_cols and col != payload.primary_key_column:
                        set_clauses.append(f"`{col}` = %s")
                        params.append(val)

                if not set_clauses:
                    raise HTTPException(status_code=400, detail="No valid editable columns provided.")

                params.append(payload.primary_key_value)
                query = f"UPDATE `{payload.table_name}` SET {', '.join(set_clauses)} WHERE `{payload.primary_key_column}` = %s"
                cur.execute(query, tuple(params))
                conn.commit()

                return {
                    "success": True,
                    "affected_rows": cur.rowcount,
                    "message": f"Successfully updated row in `{payload.table_name}`."
                }
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))

