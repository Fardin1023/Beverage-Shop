-- =============================================================================
-- Daily Drop Beverage Shop - Phase 1: Triggers & Stored Procedures
-- =============================================================================

USE daily_drop_db;

DELIMITER $$

-- Drop trigger if already exists
DROP TRIGGER IF EXISTS trg_check_low_stock_after_update$$

-- Trigger: Automatically fires when stock is updated
-- If stock drops to or below the low_stock_threshold, it logs an automated restock request
CREATE TRIGGER trg_check_low_stock_after_update
AFTER UPDATE ON shop_stock
FOR EACH ROW
BEGIN
    DECLARE v_low_thresh DECIMAL(10, 2);
    DECLARE v_existing_req_id INT DEFAULT NULL;
    DECLARE v_new_req_id INT;
    DECLARE v_item_name VARCHAR(100);

    -- Retrieve low stock threshold and item name
    SELECT low_stock_threshold, name INTO v_low_thresh, v_item_name
    FROM inventory_items
    WHERE id = NEW.inventory_item_id;

    -- Check if stock has breached low stock threshold
    IF NEW.current_quantity <= v_low_thresh THEN
        -- Check if an unfulfilled (pending) request already exists for this item
        SELECT r.id INTO v_existing_req_id
        FROM shop_restock_requests r
        JOIN shop_restock_request_items ri ON r.id = ri.request_id
        WHERE ri.inventory_item_id = NEW.inventory_item_id
          AND r.status = 'pending'
        LIMIT 1;

        -- Only create an automated restock request if one doesn't exist already
        IF v_existing_req_id IS NULL THEN
            INSERT INTO shop_restock_requests (requested_by, status, notes)
            VALUES (NEW.last_updated_by, 'pending', CONCAT('Auto-generated: low stock threshold breached for ', v_item_name, ' (Current: ', NEW.current_quantity, ')'));

            SET v_new_req_id = LAST_INSERT_ID();

            INSERT INTO shop_restock_request_items (request_id, inventory_item_id, requested_quantity, status)
            VALUES (v_new_req_id, NEW.inventory_item_id, (v_low_thresh * 2), 'pending');
        END IF;
    END IF;
END$$

-- Procedure: Atomic Order Placement
DROP PROCEDURE IF EXISTS sp_place_order$$

CREATE PROCEDURE sp_place_order(
    IN p_phone VARCHAR(20),
    IN p_menu_item_id INT,
    IN p_quantity INT,
    IN p_pickup_token VARCHAR(10),
    OUT p_order_id INT
)
proc_label: BEGIN
    DECLARE v_cust_id INT DEFAULT NULL;
    DECLARE v_stamps INT DEFAULT 0;
    DECLARE v_rewards INT DEFAULT 0;
    DECLARE v_unit_price DECIMAL(8, 2);
    DECLARE v_total DECIMAL(10, 2);

    -- Exit handler for rollback
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    -- Fetch item price
    SELECT price INTO v_unit_price FROM menu_items WHERE id = p_menu_item_id;
    IF v_unit_price IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Menu item not found';
    END IF;

    SET v_total = v_unit_price * p_quantity;

    -- Customer lookup or auto-creation
    IF p_phone IS NOT NULL AND TRIM(p_phone) <> '' THEN
        SELECT id, punch_card_stamps, rewards_earned INTO v_cust_id, v_stamps, v_rewards
        FROM customers WHERE phone = p_phone LIMIT 1;

        IF v_cust_id IS NULL THEN
            -- First visit: 1 stamp awarded
            INSERT INTO customers (phone, full_name, punch_card_stamps, rewards_earned)
            VALUES (p_phone, 'Loyal Drinker', 1, 0);
            SET v_cust_id = LAST_INSERT_ID();
        ELSE
            -- Increment stamp
            SET v_stamps = v_stamps + 1;
            IF v_stamps >= 6 THEN
                SET v_rewards = v_rewards + 1;
                SET v_stamps = 0;
            END IF;
            UPDATE customers
            SET punch_card_stamps = v_stamps, rewards_earned = v_rewards
            WHERE id = v_cust_id;
        END IF;
    END IF;

    -- Create order
    INSERT INTO orders (customer_id, pickup_token, total_amount, status)
    VALUES (v_cust_id, p_pickup_token, v_total, 'completed');
    SET p_order_id = LAST_INSERT_ID();

    -- Create order line item
    INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, subtotal)
    VALUES (p_order_id, p_menu_item_id, p_quantity, v_unit_price, v_total);

    -- Atomic BOM inventory depletion
    UPDATE shop_stock ss
    JOIN recipe_ingredients ri ON ss.inventory_item_id = ri.inventory_item_id
    SET ss.current_quantity = GREATEST(0, ss.current_quantity - (ri.quantity_required * p_quantity))
    WHERE ri.menu_item_id = p_menu_item_id;

    COMMIT;
END$$

-- Procedure: Atomic Supplier Delivery Processing
DROP PROCEDURE IF EXISTS sp_process_delivery$$

CREATE PROCEDURE sp_process_delivery(
    IN p_restock_request_id INT,
    IN p_inventory_item_id INT,
    IN p_supplier_user_id INT,
    IN p_delivery_date DATE,
    IN p_challan_number VARCHAR(50),
    IN p_unit_cost DECIMAL(10, 2),
    IN p_quantity DECIMAL(10, 2),
    OUT p_delivery_id INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    -- Record delivery
    INSERT INTO supplier_shop_deliveries (
        restock_request_id, inventory_item_id, supplier_user_id,
        delivery_date, challan_number, unit_cost, quantity
    ) VALUES (
        p_restock_request_id, p_inventory_item_id, p_supplier_user_id,
        p_delivery_date, p_challan_number, p_unit_cost, p_quantity
    );
    SET p_delivery_id = LAST_INSERT_ID();

    -- Atomically increase stock balance
    UPDATE shop_stock
    SET current_quantity = current_quantity + p_quantity,
        last_updated_by = p_supplier_user_id
    WHERE inventory_item_id = p_inventory_item_id;

    -- Mark restock request as fulfilled if linked
    IF p_restock_request_id IS NOT NULL THEN
        UPDATE shop_restock_requests
        SET status = 'fulfilled'
        WHERE id = p_restock_request_id;

        UPDATE shop_restock_request_items
        SET status = 'fulfilled'
        WHERE request_id = p_restock_request_id
          AND inventory_item_id = p_inventory_item_id;
    END IF;

    COMMIT;
END$$

DELIMITER ;
