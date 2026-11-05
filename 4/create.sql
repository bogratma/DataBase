DROP SCHEMA public CASCADE;
CREATE SCHEMA public;

CREATE TABLE IF NOT EXISTS shop(
	shop_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	address TEXT UNIQUE NOT NULL,
	cash_registers SMALLINT CHECK (cash_registers >= 0) NOT NULL,
	open_time TIME,
	close_time TIME
);

CREATE TABLE IF NOT EXISTS employee(
	employee_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	full_name TEXT NOT NULL,
	passport VARCHAR(20) UNIQUE NOT NULL,
	registration TEXT NOT NULL,
	birth_date DATE NOT NULL,
	phone VARCHAR(20) UNIQUE NOT NULL,
	education TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job(
	job_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	title TEXT UNIQUE NOT NULL,
	description TEXT,
	duties TEXT NOT NULL
);

CREATE TYPE SUPPLIER_TYPE_ENUM AS ENUM ('legal', 'sole_prop', 'individual');
CREATE TABLE IF NOT EXISTS supplier(
	supplier_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	name_ TEXT NOT NULL,
	description TEXT,
	address TEXT NOT NULL,
	supplier_type SUPPLIER_TYPE_ENUM NOT NULL
);

CREATE TABLE IF NOT EXISTS buyer(
	buyer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	full_name TEXT NOT NULL,
	email TEXT UNIQUE NOT NULL,
	phone VARCHAR(20) UNIQUE NOT NULL,
	birth_date DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS discount_card(
	buyer_id BIGINT PRIMARY KEY,
	discount_percent SMALLINT NOT NULL CHECK (discount_percent BETWEEN 0 AND 100),
	registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	CONSTRAINT fk_discount_card_buyer FOREIGN KEY (buyer_id) REFERENCES buyer(buyer_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS return_reason(
	reason_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	tag TEXT UNIQUE NOT NULL,
	is_shop_fault BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS contract(
	contract_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	worker_id BIGINT NOT NULL,
	job_id BIGINT NOT NULL,
	shop_id BIGINT NOT NULL,
	admin_id BIGINT NOT NULL,
	start_date DATE NOT NULL,
	end_date DATE,
	salary NUMERIC(12,2) NOT NULL,
	hour_ NUMERIC(12,2) NOT NULL,
	CONSTRAINT fk_contract_worker FOREIGN KEY (worker_id) REFERENCES employee(employee_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_contract_job FOREIGN KEY (job_id) REFERENCES job(job_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_contract_shop FOREIGN KEY (shop_id) REFERENCES shop(shop_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_contract_admin FOREIGN KEY (admin_id) REFERENCES employee(employee_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS schedule(
	schedule_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	contract_id BIGINT NOT NULL,
	is_working_day BOOLEAN NOT NULL,
	start_time TIME,
	end_time TIME,
	lunch_start TIME,
	lunch_end TIME,
	work_date DATE NOT NULL,
	CONSTRAINT fk_schedule_contract FOREIGN KEY (contract_id) REFERENCES contract(contract_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TYPE ROOM_TYPE_ENUM AS ENUM ('hall', 'warehouse');
CREATE TABLE IF NOT EXISTS room(
	room_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	shop_id BIGINT NOT NULL,
	room_type ROOM_TYPE_ENUM NOT NULL,
	area REAL NOT NULL CHECK (area > 0),
	rent_cost NUMERIC(12,2) NOT NULL,
	amount SMALLINT NOT NULL CHECK (amount >= 0),
	CONSTRAINT fk_room_shop FOREIGN KEY (shop_id) REFERENCES shop(shop_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TYPE GARMENT_KIND_ENUM AS ENUM ('man', 'woman', 'kid', 'usex');
CREATE TABLE IF NOT EXISTS garment(
	garment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	brand TEXT NOT NULL,
	color VARCHAR(50) NOT NULL,
	size_ VARCHAR(20) NOT NULL,
	kind GARMENT_KIND_ENUM NOT NULL,
	buy_price NUMERIC(12,2) NOT NULL,
	retail_price NUMERIC(12,2) NOT NULL,
	is_designer BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS kit(
	kit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	name_ TEXT NOT NULL,
	retail_price NUMERIC(12,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS kit_item(
	garment_id BIGINT NOT NULL,
	kit_id BIGINT NOT NULL,
	amount INTEGER NOT NULL CHECK (amount > 0),
	CONSTRAINT pk_kit_item PRIMARY KEY (garment_id, kit_id),
	CONSTRAINT fk_kit_item_garment FOREIGN KEY (garment_id) REFERENCES garment(garment_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_kit_item_kit FOREIGN KEY (kit_id) REFERENCES kit(kit_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS sale_item(
	sale_item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	garment_id BIGINT,
	kit_id BIGINT,
	CONSTRAINT fk_sale_item_garment FOREIGN KEY (garment_id) REFERENCES garment(garment_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_sale_item_kit FOREIGN KEY (kit_id) REFERENCES kit(kit_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS supply(
	supply_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	supplier_id BIGINT NOT NULL,
	shop_id BIGINT NOT NULL,
	ordered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	delivered_at TIMESTAMPTZ,
	total_cost NUMERIC(12,2) NOT NULL,
	CONSTRAINT chk_supply_dates CHECK (delivered_at IS NULL OR delivered_at >= ordered_at),
	CONSTRAINT fk_supply_supplier FOREIGN KEY (supplier_id) REFERENCES supplier(supplier_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_supply_shop FOREIGN KEY (shop_id) REFERENCES shop(shop_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS supply_item(
	supply_item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	supply_id BIGINT NOT NULL,
	garment_id BIGINT NOT NULL,
	amount INTEGER NOT NULL CHECK (amount > 0),
	unit_price NUMERIC(12,2) NOT NULL,
	CONSTRAINT fk_supply_item_supply FOREIGN KEY (supply_id) REFERENCES supply(supply_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_supply_item_garment FOREIGN KEY (garment_id) REFERENCES garment(garment_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS cheque(
	cheque_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	shop_id BIGINT NOT NULL,
	seller_id BIGINT NOT NULL,
	buyer_id BIGINT,
	discount_percent SMALLINT DEFAULT 0 CHECK (discount_percent BETWEEN 0 AND 100),
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	CONSTRAINT fk_cheque_shop FOREIGN KEY (shop_id) REFERENCES shop(shop_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_cheque_seller FOREIGN KEY (seller_id) REFERENCES employee(employee_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_cheque_buyer FOREIGN KEY (buyer_id) REFERENCES buyer(buyer_id) ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS cheque_item(
	cheque_item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	cheque_id BIGINT NOT NULL,
	sale_item_id BIGINT NOT NULL,
	amount INTEGER NOT NULL CHECK (amount > 0),
	unit_price NUMERIC(12,2) NOT NULL,
	CONSTRAINT fk_cheque_item_cheque FOREIGN KEY (cheque_id) REFERENCES cheque(cheque_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_cheque_item_sale_item FOREIGN KEY (sale_item_id) REFERENCES sale_item(sale_item_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TYPE FULFILLMENT_ENUM AS ENUM ('delivery', 'pickup');
CREATE TYPE ORDER_STATUS_ENUM AS ENUM ('new', 'postpone', 'cancel', 'done');
CREATE TYPE ORDER_CHANNEL_ENUM AS ENUM ('phone', 'internet');
CREATE TABLE IF NOT EXISTS customer_order(
	order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	shop_id BIGINT NOT NULL,
	seller_id BIGINT NOT NULL,
	buyer_id BIGINT,
	fulfil_shop_id BIGINT NOT NULL,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	fulfillment FULFILLMENT_ENUM NOT NULL,
	status ORDER_STATUS_ENUM NOT NULL DEFAULT 'new',
	comment_ TEXT,
	channel ORDER_CHANNEL_ENUM NOT NULL,
	CONSTRAINT fk_order_shop FOREIGN KEY (shop_id) REFERENCES shop(shop_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_order_seller FOREIGN KEY (seller_id) REFERENCES employee(employee_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_order_buyer FOREIGN KEY (buyer_id) REFERENCES buyer(buyer_id) ON DELETE SET NULL ON UPDATE CASCADE,
	CONSTRAINT fk_order_fulfil_shop FOREIGN KEY (fulfil_shop_id) REFERENCES shop(shop_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS order_item(
	order_item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	order_id BIGINT NOT NULL,
	sale_item_id BIGINT NOT NULL,
	amount INTEGER NOT NULL CHECK (amount > 0),
	unit_price NUMERIC(12,2) NOT NULL,
	CONSTRAINT fk_order_item_order FOREIGN KEY (order_id) REFERENCES customer_order(order_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_order_item_sale_item FOREIGN KEY (sale_item_id) REFERENCES sale_item(sale_item_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS delivery_note(
	delivery_note_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	order_id BIGINT NOT NULL,
	courier_id BIGINT NOT NULL,
	to_shop_id BIGINT,
	customer_name TEXT,
	customer_phone VARCHAR(20),
	address TEXT,
	planned_at TIMESTAMPTZ NOT NULL,
	delivered_at TIMESTAMPTZ,
	customer_signature TEXT,
	review TEXT,
	delivery_fee NUMERIC(12,2) NOT NULL,
	is_negative BOOLEAN NOT NULL DEFAULT FALSE,
	CONSTRAINT fk_delivery_note_order FOREIGN KEY (order_id) REFERENCES customer_order(order_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_delivery_note_courier FOREIGN KEY (courier_id) REFERENCES employee(employee_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_delivery_note_to_shop FOREIGN KEY (to_shop_id) REFERENCES shop(shop_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TYPE DELIVERY_ITEM_STATUS_ENUM AS ENUM ('accepted', 'refused');
CREATE TABLE IF NOT EXISTS delivery_item(
	delivery_item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	note_id BIGINT NOT NULL,
	order_item_id BIGINT NOT NULL,
	amount INTEGER NOT NULL CHECK (amount > 0),
	status DELIVERY_ITEM_STATUS_ENUM NOT NULL,
	CONSTRAINT fk_delivery_item_note FOREIGN KEY (note_id) REFERENCES delivery_note(delivery_note_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_delivery_item_order_item FOREIGN KEY (order_item_id) REFERENCES order_item(order_item_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TYPE PAYMENT_REASON_ENUM AS ENUM ('salary', 'delivery', 'bonus');
CREATE TABLE IF NOT EXISTS payment_order(
	payment_order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	contract_id BIGINT NOT NULL,
	delivery_note_id BIGINT,
	amount NUMERIC(12,2) NOT NULL,
	paid_at TIMESTAMPTZ NOT NULL,
	reason PAYMENT_REASON_ENUM NOT NULL,
	period_month DATE,
	CONSTRAINT fk_payment_order_contract FOREIGN KEY (contract_id) REFERENCES contract(contract_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_payment_order_delivery_note FOREIGN KEY (delivery_note_id) REFERENCES delivery_note(delivery_note_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS product_return(
	return_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	cheque_id BIGINT,
	order_id BIGINT,
	reason_id BIGINT NOT NULL,
	employee_id BIGINT NOT NULL,
	returned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	delivery_fee_refunded BOOLEAN NOT NULL DEFAULT FALSE,
	CONSTRAINT chk_return_fee CHECK (NOT delivery_fee_refunded OR order_id IS NOT NULL),
	CONSTRAINT fk_return_cheque FOREIGN KEY (cheque_id) REFERENCES cheque(cheque_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_return_order FOREIGN KEY (order_id) REFERENCES customer_order(order_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_return_reason FOREIGN KEY (reason_id) REFERENCES return_reason(reason_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_return_employee FOREIGN KEY (employee_id) REFERENCES employee(employee_id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TYPE RETURN_DESTINATION_ENUM AS ENUM ('stock', 'written_off');
CREATE TABLE IF NOT EXISTS return_item(
	return_item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	return_id BIGINT NOT NULL,
	cheque_item_id BIGINT,
	order_item_id BIGINT,
	amount INTEGER NOT NULL CHECK (amount > 0),
	destination RETURN_DESTINATION_ENUM NOT NULL,
	CONSTRAINT fk_return_item_return FOREIGN KEY (return_id) REFERENCES product_return(return_id) ON DELETE CASCADE ON UPDATE CASCADE,
	CONSTRAINT fk_return_item_cheque_item FOREIGN KEY (cheque_item_id) REFERENCES cheque_item(cheque_item_id) ON DELETE RESTRICT ON UPDATE CASCADE,
	CONSTRAINT fk_return_item_order_item FOREIGN KEY (order_item_id) REFERENCES order_item(order_item_id) ON DELETE RESTRICT ON UPDATE CASCADE
);