# ☕ Daily Drop Beverage Shop - Enterprise System Architecture

Complete end-to-end implementation of the **Daily Drop Beverage Shop** system spanning high-performance relational database provisioning, atomic transactions with Bill of Materials (BOM) inventory depletions, multi-role interfaces, and production operations.

---

## 🏗️ Architecture Overview

```
e:\Projects\Beverage Shop\
├── database/
│   ├── 01_schema.sql                  # Strict DDL: users -> customers -> menu_items -> inventory_items -> recipe_ingredients -> shop_stock -> orders -> order_items -> shop_restock_requests -> shop_restock_request_items -> supplier_shop_deliveries -> supplier_company_orders
│   ├── 02_triggers_procedures.sql     # trg_check_low_stock_after_update, sp_place_order, sp_process_delivery
│   ├── 03_rbac_provisioning.sql       # shop_clerk, local_supplier, company_admin with granular GRANTs
│   ├── 04_seed_data.sql               # Reference users, ingredients catalog, weekday secret drops, BOM recipes, initial stock
│   └── setup_db.py                    # Automated Python database setup & seed runner
├── backend/
│   ├── app/
│   │   ├── db.py                      # Connection pool (10-20 connections) via PyMySQL
│   │   ├── main.py                    # FastAPI application, CORS & static frontend mount
│   │   └── routers/
│   │       ├── customer.py            # Customer lookup, daily menu (with DAYOFWEEK), atomic order placement
│   │       ├── shopkeeper.py          # Stock grid, debounced stepper adjustments, instant restock alert
│   │       ├── supplier.py            # Restock requests, dispatch deliveries, central bulk requisitions
│   │       └── company.py             # Demand summary aggregation & order transition workflow
│   ├── run_server.py                  # API server runner
│   └── requirements.txt
├── frontend/
│   ├── index.html                     # Central Operations Hub & Company Admin Aggregation Dashboard
│   ├── counter/index.html             # 8-10" Tablet Counter UI with 300ms debounce & instant supplier alert
│   ├── supplier/index.html            # Mobile-friendly Local Supplier Portal with CURDATE() auto-fill & quick buttons
│   ├── customer/index.html            # Customer Storefront with 3D flip card, 6-stamp punch card & scratch reveal
│   └── shared/styles.css              # High-contrast UI theme & color-coded status pills
├── tests/
│   ├── test_integrity.py              # Phase 2: FK cascade delete, UNIQUE constraint, concurrent row-locking
│   └── test_e2e_simulation.py         # Phase 5: Complete 4-flow end-to-end automated simulation runbook
├── docker/
│   ├── Dockerfile                     # Containerized FastAPI & frontend static asset server
│   └── docker-compose.yml             # MySQL 8.0 + Backend with Slow Query Logging & volume mounts
└── backups/
    ├── backup_daily_drop.sh           # Linux cron backup script using single-transaction mysqldump
    └── backup_daily_drop.ps1          # Windows automated backup script
```

---

## 🚀 Quickstart Guide

### 1. Database Provisioning
Run the automated initialization script against your MySQL 8.0 server:
```bash
py database/setup_db.py <YOUR_MYSQL_ROOT_PASSWORD>
```

### 2. Run Backend Server
```bash
py backend/run_server.py
```
API Documentation will be live at: `http://localhost:8000/docs`

### 3. Open Frontline Portals
- **Central Operations & Hub**: `http://localhost:8000/static/index.html`
- **Counter Tablet View**: `http://localhost:8000/static/counter/index.html`
- **Supplier Dispatch Portal**: `http://localhost:8000/static/supplier/index.html`
- **Customer Loyalty Storefront**: `http://localhost:8000/static/customer/index.html`

### 4. Run Test Suites
```bash
# Phase 2: Relational Integrity & Concurrency
py tests/test_integrity.py

# Phase 5: End-to-End Business Flow Simulation
py tests/test_e2e_simulation.py
```
