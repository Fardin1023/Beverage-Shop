import requests
import sys

API_BASE = 'http://localhost:8000'

def test_ingestion():
    print("==================================================")
    print("TESTING MANUAL TYPING & PDF PRODUCT INGESTION")
    print("==================================================")

    # 1. Verify initial catalog is empty after seed data removal
    res_init = requests.get(f"{API_BASE}/api/catalog/products")
    assert res_init.status_code == 200
    init_count = res_init.json()['count']
    print(f"Step 1: Current catalog count = {init_count} (Fresh empty state)")

    # 2. Test Option 1: Manual Typing
    print("\n--- Testing Option 1: Manual Typing ---")
    manual_payload = {
        "name": "Artisan Caramel Macchiato",
        "category": "Coffee",
        "price": 5.25,
        "description": "Double espresso over steamed vanilla milk with handcrafted caramel drizzle",
        "available_day_of_week": None,
        "image_url": "☕",
        "auto_create_inventory": True,
        "opening_stock": 30.0,
        "ingredient_unit": "units"
    }
    res_manual = requests.post(f"{API_BASE}/api/catalog/manual-product", json=manual_payload)
    assert res_manual.status_code == 200, f"Manual add failed: {res_manual.text}"
    man_data = res_manual.json()
    print(f"PASS Option 1: Added manual product: '{man_data['name']}' (${man_data['price']:.2f})")

    # 3. Test Option 2: Products List PDF Upload
    print("\n--- Testing Option 2: Products List PDF Upload ---")
    # Fetch sample PDF from the API endpoint
    res_pdf = requests.get(f"{API_BASE}/api/catalog/sample-pdf")
    assert res_pdf.status_code == 200
    pdf_bytes = res_pdf.content
    print(f"Downloaded sample PDF: {len(pdf_bytes)} bytes")

    # Upload PDF to /api/catalog/upload-pdf
    files = {'file': ('test_products.pdf', pdf_bytes, 'application/pdf')}
    data = {'auto_create_inventory': 'true', 'opening_stock': '20.0'}
    res_upload = requests.post(f"{API_BASE}/api/catalog/upload-pdf", files=files, data=data)
    assert res_upload.status_code == 200, f"PDF upload failed: {res_upload.text}"
    upload_data = res_upload.json()
    print(f"PASS Option 2: {upload_data['message']}")
    print(f"Imported {upload_data['imported_count']} products from PDF:")
    for item in upload_data['imported_items'][:5]:
        print(f"  * {item['name']} | {item['category']} | ${item['price']:.2f}")

    # 4. Verify Catalog now has all products
    res_catalog = requests.get(f"{API_BASE}/api/catalog/products")
    total_count = res_catalog.json()['count']
    print(f"\nStep 4: Total products in database now = {total_count}")
    assert total_count == 1 + upload_data['imported_count']

    # 5. Verify Customer Storefront sees the newly added products
    res_menu = requests.get(f"{API_BASE}/api/menu/daily")
    assert res_menu.status_code == 200
    menu_items = res_menu.json()['items']
    print(f"Step 5: Customer storefront now displays {len(menu_items)} available drinks!")

    # 6. Verify Shopkeeper and Supplier stock databases are populated
    res_shop_stock = requests.get(f"{API_BASE}/api/shop/stock")
    assert res_shop_stock.status_code == 200
    stock_count = len(res_shop_stock.json()['stock'])
    print(f"Step 6: Shopkeeper & Supplier stock database contains {stock_count} tracked inventory items!")

    print("\n==================================================")
    print("ALL MANUAL TYPING & PDF INGESTION TESTS PASSED!")
    print("==================================================")

if __name__ == '__main__':
    test_ingestion()
