-- =============================================================================
-- Daily Drop Beverage Shop - Phase 2: Core Reference Data Ingestion & Seeding
-- =============================================================================

USE daily_drop_db;

-- 1. Initial Users (Counter Staff, Local Distributor, Central Warehouse Manager)
INSERT INTO users (id, username, password_hash, full_name, role, phone) VALUES
(1, 'alice_counter', 'pbkdf2:sha256:600000$dummyhash$counterpass', 'Alice Chen (Counter Lead)', 'counter_staff', '+15551001001'),
(2, 'bob_supplier', 'pbkdf2:sha256:600000$dummyhash$supplierpass', 'Bob Martinez (Local Distributor)', 'local_supplier', '+15552002002'),
(3, 'charlie_admin', 'pbkdf2:sha256:600000$dummyhash$adminpass', 'Charlie Davis (Warehouse Manager)', 'company_admin', '+15553003003')
ON DUPLICATE KEY UPDATE full_name = VALUES(full_name);

-- 2. Initial Customers (Phone is unique, loyalty punch card balances)
INSERT INTO customers (id, phone, full_name, punch_card_stamps, rewards_earned) VALUES
(1, '555-0101', 'Maya Lin', 4, 1),
(2, '555-0102', 'Jordan Smith', 5, 2),
(3, '555-0103', 'Samira Khan', 1, 0),
(4, '555-0104', 'David Miller', 0, 0)
ON DUPLICATE KEY UPDATE full_name = VALUES(full_name);

-- 3. Raw Ingredients Catalog
INSERT INTO inventory_items (id, name, unit, low_stock_threshold, critical_stock_threshold) VALUES
(1, 'Whole Milk', 'L', 15.00, 5.00),
(2, 'Espresso Beans', 'kg', 5.00, 2.00),
(3, 'Matcha Powder', 'kg', 2.00, 0.50),
(4, 'Cane Syrup', 'L', 4.00, 1.00),
(5, 'Boba Pearls', 'kg', 8.00, 3.00),
(6, 'Cold Brew Concentrate', 'L', 10.00, 3.00)
ON DUPLICATE KEY UPDATE unit = VALUES(unit);

-- 4. Menu Items
-- MySQL DAYOFWEEK(): 1=Sunday, 2=Monday, 3=Tuesday, 4=Wednesday, 5=Thursday, 6=Friday, 7=Saturday
-- Base items available everyday (available_day_of_week is NULL)
INSERT INTO menu_items (id, name, category, description, price, available_day_of_week, image_url) VALUES
(1, 'Espresso Shot', 'Coffee', 'Rich, double extraction craft espresso with silky golden crema.', 3.50, NULL, '☕'),
(2, 'Iced Latte', 'Coffee', 'Chilled whole milk poured over fresh double espresso shots.', 4.75, NULL, '🥛'),
(3, 'Matcha Boba Cloud', 'Specialty', 'Ceremonial Uji matcha, farm milk, brown sugar boba & vanilla cloud foam.', 5.50, NULL, '🍵'),
(4, 'Nitro Cold Brew', 'Coffee', 'Slow-steeped 18hr cold brew charged with nitrogen for micro-bubble velvet finish.', 4.50, NULL, '🧊'),
(5, 'Golden Milk Tea', 'Tea', 'Slow-brewed Assam black tea blended with whole milk and chewy boba pearls.', 4.25, NULL, '🧋'),

-- Daily Secret Drops (Exclusive to specific day of the week)
(6, 'Sunday Sunrise Citrus Fizz', 'Secret Drop', 'Cold brew concentrate infused with sparkling yuzu and honey cane syrup.', 5.00, 1, '🍊'),
(7, 'Monday Midnight Mocha Rush', 'Secret Drop', 'Double espresso, dark cacao swirl, whole milk, and cold brew float.', 5.25, 2, '🍫'),
(8, 'Tuesday Tiger Sugar Boba', 'Secret Drop', 'Torched muscovado syrup, warm brown sugar pearls, iced whole milk.', 5.75, 3, '🐯'),
(9, 'Wednesday Coconut Pandan Foam', 'Secret Drop', 'Cold brew topped with fragrant pandan and salted coconut cold foam.', 6.00, 4, '🥥'),
(10, 'Thursday Kyoto Spiced Brew', 'Secret Drop', 'Slow-drip cold brew with cinnamon bark, star anise, and cane syrup.', 5.50, 5, '✨'),
(11, 'Friday Tokyo Pistachio Latte', 'Secret Drop', 'Espresso layered with Sicilian roasted pistachio cream and whole milk.', 6.25, 6, '🌰'),
(12, 'Saturday Ube Velvet Sparkler', 'Secret Drop', 'Vibrant purple yam infusion, matcha drizzle, whole milk, and boba.', 5.75, 7, '🍠')
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- 5. Bill of Materials (BOM) linking drinks to raw inventory depletion units
-- 1 Iced Latte (menu_id=2) = 0.02 kg Espresso Beans (item=2) + 0.25 L Whole Milk (item=1) + 0.02 L Cane Syrup (item=4)
-- 1 Espresso Shot (menu_id=1) = 0.02 kg Espresso Beans (item=2)
-- 1 Matcha Boba Cloud (menu_id=3) = 0.015 kg Matcha Powder (item=3) + 0.20 L Whole Milk (item=1) + 0.05 kg Boba (item=5) + 0.02 L Cane Syrup (item=4)
-- 1 Nitro Cold Brew (menu_id=4) = 0.15 L Cold Brew Concentrate (item=6)
-- 1 Golden Milk Tea (menu_id=5) = 0.20 L Whole Milk (item=1) + 0.05 kg Boba (item=5) + 0.03 L Cane Syrup (item=4)
-- Secret Drops BOM:
-- Tokyo Pistachio Latte (menu_id=11) = 0.02 kg Espresso Beans (item=2) + 0.20 L Whole Milk (item=1) + 0.02 L Cane Syrup (item=4)
-- Tuesday Tiger Sugar Boba (menu_id=8) = 0.20 L Whole Milk (item=1) + 0.08 kg Boba Pearls (item=5) + 0.03 L Cane Syrup (item=4)
-- Thursday Kyoto Spiced Brew (menu_id=10) = 0.15 L Cold Brew Concentrate (item=6) + 0.02 L Cane Syrup (item=4)
-- Wednesday Coconut Pandan Foam (menu_id=9) = 0.15 L Cold Brew Concentrate (item=6) + 0.05 L Whole Milk (item=1) + 0.02 L Cane Syrup (item=4)
-- Sunday Sunrise Citrus Fizz (menu_id=6) = 0.10 L Cold Brew Concentrate (item=6) + 0.02 L Cane Syrup (item=4)
-- Monday Midnight Mocha Rush (menu_id=7) = 0.02 kg Espresso Beans (item=2) + 0.15 L Whole Milk (item=1) + 0.05 L Cold Brew (item=6)
-- Saturday Ube Velvet Sparkler (menu_id=12) = 0.20 L Whole Milk (item=1) + 0.05 kg Boba (item=5) + 0.01 kg Matcha (item=3)

INSERT INTO recipe_ingredients (menu_item_id, inventory_item_id, quantity_required) VALUES
(1, 2, 0.0200), -- Espresso: 0.02 kg Beans
(2, 1, 0.2500), -- Iced Latte: 0.25 L Milk
(2, 2, 0.0200), -- Iced Latte: 0.02 kg Beans
(2, 4, 0.0200), -- Iced Latte: 0.02 L Syrup
(3, 1, 0.2000), -- Matcha Boba: 0.20 L Milk
(3, 3, 0.0150), -- Matcha Boba: 0.015 kg Matcha
(3, 4, 0.0200), -- Matcha Boba: 0.02 L Syrup
(3, 5, 0.0500), -- Matcha Boba: 0.05 kg Boba
(4, 6, 0.1500), -- Nitro Cold Brew: 0.15 L Cold Brew
(5, 1, 0.2000), -- Milk Tea: 0.20 L Milk
(5, 4, 0.0300), -- Milk Tea: 0.03 L Syrup
(5, 5, 0.0500), -- Milk Tea: 0.05 kg Boba
(6, 6, 0.1000), -- Sunday Fizz: Cold Brew
(6, 4, 0.0200), -- Sunday Fizz: Syrup
(7, 1, 0.1500), -- Monday Mocha: Milk
(7, 2, 0.0200), -- Monday Mocha: Beans
(7, 6, 0.0500), -- Monday Mocha: Cold brew
(8, 1, 0.2000), -- Tuesday Tiger: Milk
(8, 4, 0.0300), -- Tuesday Tiger: Syrup
(8, 5, 0.0800), -- Tuesday Tiger: Boba
(9, 6, 0.1500), -- Wed Pandan: Cold Brew
(9, 1, 0.0500), -- Wed Pandan: Milk
(9, 4, 0.0200), -- Wed Pandan: Syrup
(10, 6, 0.1500), -- Thu Kyoto: Cold Brew
(10, 4, 0.0200), -- Thu Kyoto: Syrup
(11, 1, 0.2000), -- Fri Pistachio: Milk
(11, 2, 0.0200), -- Fri Pistachio: Beans
(11, 4, 0.0200), -- Fri Pistachio: Syrup
(12, 1, 0.2000), -- Sat Ube: Milk
(12, 3, 0.0100), -- Sat Ube: Matcha
(12, 5, 0.0500)  -- Sat Ube: Boba
ON DUPLICATE KEY UPDATE quantity_required = VALUES(quantity_required);

-- 6. Initial Stock Snapshot (Attached to responsible Counter Staff Alice ID: 1)
INSERT INTO shop_stock (inventory_item_id, current_quantity, last_updated_by) VALUES
(1, 25.00, 1), -- Whole Milk (25 Liters) - OK
(2, 10.00, 1), -- Espresso Beans (10 kg) - OK
(3, 4.00, 1),  -- Matcha Powder (4 kg) - OK
(4, 8.00, 1),  -- Cane Syrup (8 Liters) - OK
(5, 12.00, 1), -- Boba Pearls (12 kg) - OK
(6, 18.00, 1)  -- Cold Brew Concentrate (18 Liters) - OK
ON DUPLICATE KEY UPDATE current_quantity = VALUES(current_quantity);

-- 7. Seed Past Order History (For Customer Favorites and aggregates)
INSERT INTO orders (id, customer_id, pickup_token, total_amount, status, created_at) VALUES
(1, 1, 'TK-8821', 9.50, 'completed', NOW() - INTERVAL 5 DAY),
(2, 1, 'TK-8822', 4.75, 'completed', NOW() - INTERVAL 3 DAY),
(3, 1, 'TK-8823', 4.75, 'completed', NOW() - INTERVAL 1 DAY),
(4, 2, 'TK-7701', 5.50, 'completed', NOW() - INTERVAL 2 DAY),
(5, 2, 'TK-7702', 11.00, 'completed', NOW() - INTERVAL 1 DAY)
ON DUPLICATE KEY UPDATE pickup_token = VALUES(pickup_token);

INSERT INTO order_items (id, order_id, menu_item_id, quantity, unit_price, subtotal) VALUES
(1, 1, 2, 2, 4.75, 9.50),  -- Maya ordered 2 Iced Lattes
(2, 2, 2, 1, 4.75, 4.75),  -- Maya ordered 1 Iced Latte
(3, 3, 2, 1, 4.75, 4.75),  -- Maya ordered 1 Iced Latte (Favorite: Iced Latte!)
(4, 4, 3, 1, 5.50, 5.50),  -- Jordan ordered 1 Matcha Boba Cloud
(5, 5, 3, 2, 5.50, 11.00)  -- Jordan ordered 2 Matcha Boba Clouds (Favorite: Matcha Boba!)
ON DUPLICATE KEY UPDATE subtotal = VALUES(subtotal);
