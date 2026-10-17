import threading
import time
import os
import sys
import pymysql

# Database connection details
DB_HOST = os.environ.get('MYSQL_HOST', 'localhost')
DB_PORT = int(os.environ.get('MYSQL_PORT', 3306))
DB_USER = os.environ.get('MYSQL_USER', 'root')
DB_PASSWORD = os.environ.get('MYSQL_PASSWORD', os.environ.get('MYSQL_ROOT_PASSWORD', 'X@rV#mTk'))
DB_NAME = os.environ.get('MYSQL_DATABASE', 'daily_drop_db')

def get_raw_conn():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4',
        autocommit=False
    )

def test_fk_cascade_delete():
    print("\n--- TEST 1: Foreign Key Cascading Delete on Orders -> Order Items ---")
    conn = get_raw_conn()
    cur = conn.cursor()
    try:
        # 1. Create a dummy order
        cur.execute("INSERT INTO orders (customer_id, pickup_token, total_amount, status) VALUES (NULL, 'TEST-CASCADE', 10.00, 'completed')")
        order_id = cur.lastrowid

        # 2. Add order items
        cur.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, subtotal) VALUES (%s, 1, 2, 5.00, 10.00)", (order_id,))
        conn.commit()

        # Check item exists
        cur.execute("SELECT COUNT(*) FROM order_items WHERE order_id = %s", (order_id,))
        count_before = cur.fetchone()[0]
        assert count_before == 1, f"Expected 1 item, got {count_before}"
        print(f"Order #{order_id} created with {count_before} line item.")

        # 3. Delete parent order
        cur.execute("DELETE FROM orders WHERE id = %s", (order_id,))
        conn.commit()

        # 4. Verify line item was automatically cascaded
        cur.execute("SELECT COUNT(*) FROM order_items WHERE order_id = %s", (order_id,))
        count_after = cur.fetchone()[0]
        assert count_after == 0, f"Expected 0 items after cascade delete, got {count_after}"
        print(f"PASS: Order #{order_id} deleted -> child order_items cascaded successfully (remaining: {count_after})!")
    finally:
        cur.close()
        conn.close()

def test_unique_constraints():
    print("\n--- TEST 2: UNIQUE Constraints on Phone Numbers ---")
    conn = get_raw_conn()
    cur = conn.cursor()
    try:
        # Test customer phone unique constraint
        cur.execute("INSERT INTO customers (phone, full_name) VALUES ('555-TEST-999', 'Original User')")
        conn.commit()

        duplicate_failed = False
        try:
            cur.execute("INSERT INTO customers (phone, full_name) VALUES ('555-TEST-999', 'Duplicate User')")
            conn.commit()
        except pymysql.err.IntegrityError as e:
            duplicate_failed = True
            conn.rollback()
            print(f"PASS: Customer UNIQUE phone constraint caught duplicate: {e.args[1]}")

        assert duplicate_failed, "Expected IntegrityError on duplicate customer phone!"

        # Clean up
        cur.execute("DELETE FROM customers WHERE phone = '555-TEST-999'")
        conn.commit()
    finally:
        cur.close()
        conn.close()

def test_concurrent_row_locking():
    print("\n--- TEST 3: Simultaneous Update Tests on shop_stock (Row-level Locking) ---")
    errors = []
    successes = []

    def worker_update(worker_id):
        try:
            w_conn = get_raw_conn()
            w_cur = w_conn.cursor()
            w_cur.execute("""
                UPDATE shop_stock 
                SET current_quantity = current_quantity + 0.10
                WHERE inventory_item_id = 1
            """)
            w_conn.commit()
            w_cur.close()
            w_conn.close()
            successes.append(worker_id)
        except Exception as e:
            errors.append((worker_id, str(e)))

    threads = []
    # Launch 10 concurrent update threads on the same stock row
    for i in range(10):
        t = threading.Thread(target=worker_update, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print(f"Concurrent updates: {len(successes)} succeeded, {len(errors)} errors.")
    assert len(errors) == 0, f"Encountered deadlocks or concurrency errors: {errors}"
    print("PASS: Row-level locking executed cleanly without deadlocks!")

def run_all_integrity_tests():
    print("==================================================")
    print("PHASE 2: RELATIONAL INTEGRITY & CONSTRAINT TESTING")
    print("==================================================")
    test_fk_cascade_delete()
    test_unique_constraints()
    test_concurrent_row_locking()
    print("\nALL PHASE 2 INTEGRITY TESTS PASSED!")

if __name__ == '__main__':
    run_all_integrity_tests()
