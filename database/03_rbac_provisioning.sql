-- =============================================================================
-- Daily Drop Beverage Shop - Phase 1: RBAC Provisioning
-- Database user accounts with granular GRANT statements
-- =============================================================================

-- 1. Counter Shop Clerk
CREATE USER IF NOT EXISTS 'shop_clerk'@'%' IDENTIFIED BY 'ShopClerk2026!';
CREATE USER IF NOT EXISTS 'shop_clerk'@'localhost' IDENTIFIED BY 'ShopClerk2026!';

GRANT SELECT ON daily_drop_db.menu_items TO 'shop_clerk'@'%', 'shop_clerk'@'localhost';
GRANT SELECT, INSERT, UPDATE ON daily_drop_db.customers TO 'shop_clerk'@'%', 'shop_clerk'@'localhost';
GRANT SELECT, INSERT ON daily_drop_db.orders TO 'shop_clerk'@'%', 'shop_clerk'@'localhost';
GRANT SELECT, INSERT ON daily_drop_db.order_items TO 'shop_clerk'@'%', 'shop_clerk'@'localhost';
GRANT SELECT, UPDATE ON daily_drop_db.shop_stock TO 'shop_clerk'@'%', 'shop_clerk'@'localhost';
GRANT SELECT ON daily_drop_db.inventory_items TO 'shop_clerk'@'%', 'shop_clerk'@'localhost';
GRANT SELECT, INSERT ON daily_drop_db.shop_restock_requests TO 'shop_clerk'@'%', 'shop_clerk'@'localhost';
GRANT SELECT, INSERT ON daily_drop_db.shop_restock_request_items TO 'shop_clerk'@'%', 'shop_clerk'@'localhost';
GRANT EXECUTE ON PROCEDURE daily_drop_db.sp_place_order TO 'shop_clerk'@'%', 'shop_clerk'@'localhost';

-- 2. Local Distributor / Supplier
CREATE USER IF NOT EXISTS 'local_supplier'@'%' IDENTIFIED BY 'LocalSupplier2026!';
CREATE USER IF NOT EXISTS 'local_supplier'@'localhost' IDENTIFIED BY 'LocalSupplier2026!';

GRANT SELECT ON daily_drop_db.inventory_items TO 'local_supplier'@'%', 'local_supplier'@'localhost';
GRANT SELECT, UPDATE ON daily_drop_db.shop_restock_requests TO 'local_supplier'@'%', 'local_supplier'@'localhost';
GRANT SELECT, UPDATE ON daily_drop_db.shop_restock_request_items TO 'local_supplier'@'%', 'local_supplier'@'localhost';
GRANT SELECT, INSERT ON daily_drop_db.supplier_shop_deliveries TO 'local_supplier'@'%', 'local_supplier'@'localhost';
GRANT SELECT, INSERT ON daily_drop_db.supplier_company_orders TO 'local_supplier'@'%', 'local_supplier'@'localhost';
GRANT SELECT, UPDATE ON daily_drop_db.shop_stock TO 'local_supplier'@'%', 'local_supplier'@'localhost';
GRANT EXECUTE ON PROCEDURE daily_drop_db.sp_process_delivery TO 'local_supplier'@'%', 'local_supplier'@'localhost';

-- 3. Central Warehouse / Company Admin
CREATE USER IF NOT EXISTS 'company_admin'@'%' IDENTIFIED BY 'CompanyAdmin2026!';
CREATE USER IF NOT EXISTS 'company_admin'@'localhost' IDENTIFIED BY 'CompanyAdmin2026!';

GRANT ALL PRIVILEGES ON daily_drop_db.* TO 'company_admin'@'%', 'company_admin'@'localhost' WITH GRANT OPTION;
GRANT PROCESS, SHOW VIEW ON *.* TO 'company_admin'@'%', 'company_admin'@'localhost';

FLUSH PRIVILEGES;
