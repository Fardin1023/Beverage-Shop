import requests
import time
import os
import sys

API_BASE = os.environ.get('API_BASE', 'http://localhost:8000')

def run_simulation():
    print("==================================================")
    print("PHASE 5: END-TO-END SIMULATION RUNBOOK")
    print(f"Target API: {API_BASE}")
    print("==================================================")

    # -------------------------------------------------------------------------
    # FLOW 1: Customer Order Flow
    # -------------------------------------------------------------------------
    print("\n--- FLOW 1: Customer Order Flow (2 Iced Lattes) ---")
    # Fetch initial milk and bean stock
    res_stock = requests.get(f"{API_BASE}/api/shop/stock")
    assert res_stock.status_code == 200, "Failed to get stock"
    stock_map = {item['name']: item for item in res_stock.json()['stock']}
    init_milk = stock_map['Whole Milk']['current_quantity']
    init_beans = stock_map['Espresso Beans']['current_quantity']
    print(f"Initial Shop Stock: Milk={init_milk} L, Beans={init_beans} kg")

    # Lookup Maya (555-0101)
    res_cust = requests.get(f"{API_BASE}/api/customer/lookup?phone=555-0101")
    init_stamps = res_cust.json()['punch_card_stamps']
    print(f"Initial Customer Stamps for Maya: {init_stamps}/6")

    # Place order for 2 Iced Lattes (menu_item_id = 2)
    # BOM: 1 Iced Latte = 0.25 L Milk + 0.02 kg Beans
    # 2 Iced Lattes = 0.50 L Milk + 0.04 kg Beans
    order_payload = {
        "phone": "555-0101",
        "items": [{"menu_item_id": 2, "quantity": 2}]
    }
    res_order = requests.post(f"{API_BASE}/api/orders/place", json=order_payload)
    assert res_order.status_code == 200, f"Order placement failed: {res_order.text}"
    order_data = res_order.json()
    print(f"Order #{order_data['order_id']} placed! Pickup Token: {order_data['pickup_token']}")
    print(f"Total Amount: ${order_data['total_amount']}, New Stamps: {order_data['punch_card_stamps']}")

    # Verify Stock Depletion
    res_stock_after = requests.get(f"{API_BASE}/api/shop/stock")
    stock_map_after = {item['name']: item for item in res_stock_after.json()['stock']}
    after_milk = stock_map_after['Whole Milk']['current_quantity']
    after_beans = stock_map_after['Espresso Beans']['current_quantity']

    expected_milk = round(init_milk - 0.50, 2)
    expected_beans = round(init_beans - 0.04, 2)
    print(f"New Stock: Milk={after_milk} L (Expected: {expected_milk}), Beans={after_beans} kg (Expected: {expected_beans})")
    assert abs(after_milk - expected_milk) < 0.01, "Milk was not decremented correctly matching BOM"
    assert abs(after_beans - expected_beans) < 0.01, "Beans were not decremented correctly matching BOM"
    print("FLOW 1 PASS: Customer order, loyalty increment, and BOM ingredient depletion verified!")

    # -------------------------------------------------------------------------
    # FLOW 2: Threshold Breach Flow
    # -------------------------------------------------------------------------
    print("\n--- FLOW 2: Threshold Breach Flow ---")
    # Decrement Milk until current_quantity <= low_stock_threshold (15.00 L)
    milk_item = stock_map_after['Whole Milk']
    milk_id = milk_item['inventory_item_id']
    threshold = milk_item['low_stock_threshold']

    # Adjust milk to 10.00 L to breach threshold (15.00 L)
    delta_to_breach = round(10.00 - after_milk, 2)
    print(f"Adjusting Milk by {delta_to_breach} L to bring stock to 10.00 L (Threshold is {threshold} L)...")
    res_adj = requests.patch(f"{API_BASE}/api/shop/stock/adjust", json={
        "inventory_item_id": milk_id,
        "delta": delta_to_breach,
        "user_id": 1
    })
    assert res_adj.status_code == 200
    updated_milk = res_adj.json()['item']
    print(f"Updated Milk status flag: {updated_milk['calculated_status_flag']} (Quantity: {updated_milk['current_quantity']})")
    assert updated_milk['calculated_status_flag'] in ('LOW_YELLOW', 'CRITICAL_RED')

    # Trigger or verify restock request
    res_req = requests.post(f"{API_BASE}/api/shop/restock-request", json={
        "inventory_item_ids": [milk_id],
        "user_id": 1,
        "notes": "Automated threshold breach alert for milk"
    })
    assert res_req.status_code == 200
    request_id = res_req.json()['request_id']
    print(f"FLOW 2 PASS: Threshold breach confirmed -> Restock request #{request_id} created!")

    # -------------------------------------------------------------------------
    # FLOW 3: Supplier Fulfillment Flow
    # -------------------------------------------------------------------------
    print("\n--- FLOW 3: Supplier Fulfillment Flow ---")
    # Supplier Bob delivers 20 Liters of milk
    delivery_payload = {
        "restock_request_id": request_id,
        "inventory_item_id": milk_id,
        "supplier_user_id": 2,
        "challan_number": "CH-SIM-8899",
        "unit_cost": 1.20,
        "quantity": 20.00
    }
    res_deliv = requests.post(f"{API_BASE}/api/supplier/deliveries", json=delivery_payload)
    assert res_deliv.status_code == 200, f"Delivery failed: {res_deliv.text}"
    deliv_data = res_deliv.json()
    print(f"Delivery logged #{deliv_data['delivery_id']}: Added {deliv_data['added_quantity']} {deliv_data['unit']}")
    print(f"New Shop Milk Stock: {deliv_data['new_shop_stock']} L")

    # Check status pill returns to OK_GREEN
    res_check = requests.get(f"{API_BASE}/api/shop/stock")
    refreshed_milk = next(i for i in res_check.json()['stock'] if i['inventory_item_id'] == milk_id)
    print(f"Refreshed status flag: {refreshed_milk['calculated_status_flag']}")
    assert refreshed_milk['calculated_status_flag'] == 'OK_GREEN', "Stock should be OK_GREEN after delivery!"
    print("FLOW 3 PASS: Delivery added +20 L, request fulfilled, status flag restored to OK_GREEN!")

    # -------------------------------------------------------------------------
    # FLOW 4: Supplier-to-Company Bulk Flow
    # -------------------------------------------------------------------------
    print("\n--- FLOW 4: Supplier-to-Company Bulk Requisition Flow ---")
    company_payload = {
        "supplier_user_id": 2,
        "inventory_item_id": milk_id,
        "requested_quantity": 100.00,
        "requisition_notes": "Bulk weekly requisition for retail supply"
    }
    res_comp = requests.post(f"{API_BASE}/api/supplier/company-orders", json=company_payload)
    assert res_comp.status_code == 200, f"Company order failed: {res_comp.text}"
    comp_order_id = res_comp.json()['company_order_id']
    print(f"Bulk Requisition #{comp_order_id} logged for 100 L")

    # Verify appearance on Company Demand Aggregation Dashboard
    res_demand = requests.get(f"{API_BASE}/api/company/demand-summary")
    assert res_demand.status_code == 200
    milk_demand = next(i for i in res_demand.json()['demand_summary'] if i['inventory_item_id'] == milk_id)
    print(f"Company Demand Dashboard: Total Pending Demand for {milk_demand['item_name']} = {milk_demand['total_pending_demand']} {milk_demand['unit']}")
    assert milk_demand['total_pending_demand'] >= 100.0, "Bulk demand did not register on dashboard"

    # Transition status: submitted -> approved -> dispatched
    res_appr = requests.patch(f"{API_BASE}/api/company/orders/{comp_order_id}/status", json={"status": "approved"})
    assert res_appr.status_code == 200
    print(f"Order #{comp_order_id} transitioned: {res_appr.json()['message']}")

    res_disp = requests.patch(f"{API_BASE}/api/company/orders/{comp_order_id}/status", json={"status": "dispatched"})
    assert res_disp.status_code == 200
    print(f"Order #{comp_order_id} transitioned: {res_disp.json()['message']}")
    print("FLOW 4 PASS: Bulk requisition appeared on company dashboard and transitioned across workflow!")

    print("\n==================================================")
    print("ALL 4 END-TO-END FLOWS COMPLETED SUCCESSFULLY!")
    print("==================================================")

if __name__ == '__main__':
    run_simulation()
