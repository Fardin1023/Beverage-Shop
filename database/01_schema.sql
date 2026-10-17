-- =============================================================================
-- Daily Drop Beverage Shop - Phase 1: Database Initialization DDL
-- Engine: MySQL 8.0+ | Storage Engine: InnoDB | Charset: utf8mb4
-- Strict Dependency Order:
--   users -> customers -> menu_items -> inventory_items -> recipe_ingredients
--   -> shop_stock -> orders -> order_items -> shop_restock_requests
--   -> shop_restock_request_items -> supplier_shop_deliveries
--   -> supplier_company_orders
-- =============================================================================

CREATE DATABASE IF NOT EXISTS daily_drop_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE daily_drop_db;

-- 1. Users table (Counter staff, local distributor, central warehouse manager)
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role ENUM('counter_staff', 'local_supplier', 'company_admin') NOT NULL,
    phone VARCHAR(20) NOT NULL UNIQUE,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Customers table (Phone is unique, 6-stamp punch card loyalty tracker)
CREATE TABLE IF NOT EXISTS customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    phone VARCHAR(20) NOT NULL UNIQUE,
    full_name VARCHAR(100) NOT NULL DEFAULT 'Guest Drinker',
    punch_card_stamps INT NOT NULL DEFAULT 0,
    rewards_earned INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_cust_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Menu Items (Standard items + weekday-specific Secret Drops via available_day_of_week)
-- MySQL DAYOFWEEK(): 1=Sunday, 2=Monday, 3=Tuesday, 4=Wednesday, 5=Thursday, 6=Friday, 7=Saturday
-- NULL available_day_of_week means available every day
CREATE TABLE IF NOT EXISTS menu_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category ENUM('Coffee', 'Tea', 'Specialty', 'Secret Drop') NOT NULL,
    description TEXT,
    price DECIMAL(8, 2) NOT NULL,
    available_day_of_week TINYINT NULL COMMENT '1=Sunday..7=Saturday. NULL=Everyday',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    image_url VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_menu_avail (is_active, available_day_of_week)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Raw Ingredients Catalog
CREATE TABLE IF NOT EXISTS inventory_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    unit VARCHAR(20) NOT NULL COMMENT 'kg, L, g, units',
    low_stock_threshold DECIMAL(10, 2) NOT NULL DEFAULT 10.00,
    critical_stock_threshold DECIMAL(10, 2) NOT NULL DEFAULT 5.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Bill of Materials (BOM) linking drinks to raw inventory depletion units
CREATE TABLE IF NOT EXISTS recipe_ingredients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    menu_item_id INT NOT NULL,
    inventory_item_id INT NOT NULL,
    quantity_required DECIMAL(10, 4) NOT NULL COMMENT 'Depletion amount per single drink',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_recipe_menu_item FOREIGN KEY (menu_item_id)
        REFERENCES menu_items (id) ON DELETE CASCADE,
    CONSTRAINT fk_recipe_inventory_item FOREIGN KEY (inventory_item_id)
        REFERENCES inventory_items (id) ON DELETE RESTRICT,
    UNIQUE KEY uq_menu_inventory (menu_item_id, inventory_item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Shop Stock Snapshot (Current balances and staff accountability)
CREATE TABLE IF NOT EXISTS shop_stock (
    id INT AUTO_INCREMENT PRIMARY KEY,
    inventory_item_id INT NOT NULL UNIQUE,
    current_quantity DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    last_updated_by INT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_stock_inventory_item FOREIGN KEY (inventory_item_id)
        REFERENCES inventory_items (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_last_user FOREIGN KEY (last_updated_by)
        REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Orders table (Short alphanumeric pickup token)
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NULL,
    pickup_token VARCHAR(20) NOT NULL UNIQUE,
    total_amount DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    status ENUM('pending', 'completed', 'cancelled') NOT NULL DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id)
        REFERENCES customers (id) ON DELETE SET NULL,
    INDEX idx_orders_pickup (pickup_token),
    INDEX idx_orders_cust (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Order Items table (With cascading delete)
CREATE TABLE IF NOT EXISTS order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    menu_item_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    unit_price DECIMAL(8, 2) NOT NULL,
    subtotal DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_order_items_order FOREIGN KEY (order_id)
        REFERENCES orders (id) ON DELETE CASCADE,
    CONSTRAINT fk_order_items_menu FOREIGN KEY (menu_item_id)
        REFERENCES menu_items (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. Shop Restock Requests
CREATE TABLE IF NOT EXISTS shop_restock_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    requested_by INT NULL,
    status ENUM('pending', 'fulfilled', 'cancelled') NOT NULL DEFAULT 'pending',
    notes TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_restock_req_user FOREIGN KEY (requested_by)
        REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. Shop Restock Request Items
CREATE TABLE IF NOT EXISTS shop_restock_request_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT NOT NULL,
    inventory_item_id INT NOT NULL,
    requested_quantity DECIMAL(10, 2) NOT NULL,
    status ENUM('pending', 'fulfilled', 'cancelled') NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_req_item_request FOREIGN KEY (request_id)
        REFERENCES shop_restock_requests (id) ON DELETE CASCADE,
    CONSTRAINT fk_req_item_inventory FOREIGN KEY (inventory_item_id)
        REFERENCES inventory_items (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 11. Supplier Shop Deliveries
CREATE TABLE IF NOT EXISTS supplier_shop_deliveries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restock_request_id INT NULL,
    inventory_item_id INT NOT NULL,
    supplier_user_id INT NULL,
    delivery_date DATE NOT NULL,
    challan_number VARCHAR(50) NOT NULL,
    unit_cost DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    quantity DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_delivery_request FOREIGN KEY (restock_request_id)
        REFERENCES shop_restock_requests (id) ON DELETE SET NULL,
    CONSTRAINT fk_delivery_inventory FOREIGN KEY (inventory_item_id)
        REFERENCES inventory_items (id) ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_supplier FOREIGN KEY (supplier_user_id)
        REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 12. Supplier Company Orders (Requisitions from Central Warehouse)
CREATE TABLE IF NOT EXISTS supplier_company_orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    supplier_user_id INT NOT NULL,
    inventory_item_id INT NOT NULL,
    requested_quantity DECIMAL(10, 2) NOT NULL,
    status ENUM('submitted', 'approved', 'dispatched', 'delivered', 'rejected') NOT NULL DEFAULT 'submitted',
    requisition_notes TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_comp_order_supplier FOREIGN KEY (supplier_user_id)
        REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_comp_order_inventory FOREIGN KEY (inventory_item_id)
        REFERENCES inventory_items (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
