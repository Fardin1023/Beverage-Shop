import pymysql

conn = pymysql.connect(
    host='localhost',
    user='root',
    password='X@rV#mTk',
    database='daily_drop_db',
    autocommit=True
)

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

with conn.cursor() as cur:
    cur.execute("SHOW FULL PROCESSLIST")
    for row in cur.fetchall():
        if row[7] and ('ALTER' in str(row[7]) or 'Waiting for table metadata lock' in str(row[6])):
            try:
                cur.execute(f"KILL {row[0]}")
            except Exception:
                pass

    cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
    for tbl in tables:
        cur.execute(f"DELETE FROM `{tbl}`;")
        print(f"Cleared table: {tbl}")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1;")

    # Check row counts
    print("\n--- Current Table Counts ---")
    for tbl in tables:
        cur.execute(f"SELECT COUNT(*) as cnt FROM `{tbl}`;")
        count = cur.fetchone()[0]
        print(f"{tbl}: {count} rows")

print("\nAll seed data successfully removed!")
conn.close()
