import requests

API_BASE = 'http://localhost:8000'

def test_features():
    print("==================================================")
    print("VERIFYING NEW ROLE-BASED ACCESS & SUPPLY WORKFLOWS")
    print("==================================================")

    # 1. Test sales demand endpoint for shopkeeper
    res1 = requests.get(f'{API_BASE}/api/shop/sales-demand')
    assert res1.status_code == 200, f'sales-demand failed: {res1.text}'
    summary = res1.json()['summary']
    print(f"PASS 1: /api/shop/sales-demand returns summary: {summary}")

    # Fetch valid active inventory item id from shop stock
    stocks_res = requests.get(f'{API_BASE}/api/supplier/shop-stock')
    assert stocks_res.status_code == 200
    stocks = stocks_res.json()['stock']
    assert len(stocks) > 0
    active_item_id = stocks[0]['inventory_item_id']

    # 2. Test shopkeeper stock addition restriction (can only add via supplier)
    res2 = requests.patch(f'{API_BASE}/api/shop/stock/adjust', json={
        'inventory_item_id': active_item_id,
        'delta': 1.0,
        'user_id': 1
    })
    assert res2.status_code == 403, f'Stock addition was not blocked: {res2.status_code}'
    print(f"PASS 2: Positive stock adjustment (+1.00) by shopkeeper blocked with 403: {res2.json()['detail']}")

    # 2b. Test shopkeeper spill/waste decrement (allowed)
    res2b = requests.patch(f'{API_BASE}/api/shop/stock/adjust', json={
        'inventory_item_id': active_item_id,
        'delta': -0.1,
        'user_id': 1
    })
    assert res2b.status_code == 200, f'Stock decrement failed: {res2b.text}'
    print(f"PASS 2b: Spill decrement (-0.10) allowed: {res2b.json()['item']['current_quantity']} remaining")

    # 3. Test supplier access to shopkeeper's stock database
    print(f"PASS 3: Supplier view of shop stock database returned {len(stocks)} items")

    # 4. Test supplier adding product quantity (authorized)
    res4 = requests.post(f'{API_BASE}/api/supplier/deliveries', json={
        'inventory_item_id': active_item_id,
        'quantity': 10.0,
        'challan_number': 'TEST-CH-999',
        'unit_cost': 2.50,
        'supplier_user_id': 2
    })
    assert res4.status_code == 200
    print(f"PASS 4: Supplier successfully added product quantity: {res4.json()['added_quantity']} {res4.json()['unit']}")

    # 5. Test company access to supplier deliveries database
    res5 = requests.get(f'{API_BASE}/api/company/supplier-deliveries')
    assert res5.status_code == 200
    deliveries = res5.json()['deliveries']
    assert any(d['challan_number'] == 'TEST-CH-999' for d in deliveries)
    print(f"PASS 5: Company has full visibility into supplier deliveries database ({len(deliveries)} deliveries logged)")

    # 6. Test supplier asking stock from company & Company give/not-give option
    req_res = requests.post(f'{API_BASE}/api/supplier/company-orders', json={
        'supplier_user_id': 2,
        'inventory_item_id': active_item_id,
        'requested_quantity': 50,
        'requisition_notes': 'Weekend bulk requisition'
    })
    assert req_res.status_code == 200
    order_id = req_res.json()['company_order_id']
    print(f"PASS 6a: Supplier successfully asked stock from company (Requisition #{order_id})")

    # Company declines / rejects (Option to NOT give stock)
    rej_res = requests.patch(f'{API_BASE}/api/company/orders/{order_id}/status', json={'status': 'rejected'})
    assert rej_res.status_code == 200
    assert rej_res.json()['new_status'] == 'rejected'
    print(f"PASS 6b: Company exercised option NOT to give stock -> Order #{order_id} marked 'rejected'")

    # Supplier checks status to see rejection
    sup_orders = requests.get(f'{API_BASE}/api/supplier/company-orders?supplier_id=2').json()['orders']
    my_order = next(o for o in sup_orders if o['id'] == order_id)
    assert my_order['status'] == 'rejected'
    print(f"PASS 6c: Supplier sees that company rejected the request: status = {my_order['status']}")

    # Another requisition where company GIVES stock (Approves)
    req_res2 = requests.post(f'{API_BASE}/api/supplier/company-orders', json={
        'supplier_user_id': 2,
        'inventory_item_id': active_item_id,
        'requested_quantity': 25,
        'requisition_notes': 'Stock replenishment'
    })
    order_id2 = req_res2.json()['company_order_id']
    appr_res = requests.patch(f'{API_BASE}/api/company/orders/{order_id2}/status', json={'status': 'approved'})
    assert appr_res.status_code == 200
    assert appr_res.json()['new_status'] == 'approved'
    print(f"PASS 6d: Company exercised option to GIVE stock -> Order #{order_id2} marked 'approved'")

    print("\n==================================================")
    print("ALL VERIFICATION CHECKS PASSED PERFECTLY!")
    print("==================================================")

if __name__ == '__main__':
    test_features()
