#!/usr/bin/env python3


from __future__ import annotations

import argparse
import re
from pathlib import Path
from dataclasses import dataclass
import random
import sys
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

# Fixed reference date makes the entire output reproducible for a given seed.
REFERENCE_TIME = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)

# Identity columns from the clothing_store schema. Foreign keys such as
# discount_card.buyer_id are deliberately excluded.
IDENTITY_COLUMNS = {
    table: f"{table}_id" for table in (
        "shop", "employee", "job", "supplier", "buyer", "contract",
        "schedule", "room", "garment", "kit", "sale_item", "supply",
        "supply_item", "cheque", "cheque_item", "order_item",
        "delivery_note", "delivery_item", "payment_order", "return_item",
    )
}
IDENTITY_COLUMNS.update({
    "return_reason": "reason_id", "customer_order": "order_id",
    "product_return": "return_id",
})

@dataclass(frozen=True)
class Reference:
    name: str
    value: int


def literal(value: Any) -> str:
    if isinstance(value, Reference):
        return str(value.value)
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        value = value.isoformat()
    if isinstance(value, str):
        if "\x00" in value:
            raise ValueError("PostgreSQL strings cannot contain NUL")
        return "'" + value.replace("'", "''") + "'"
    raise TypeError(f"Unsupported SQL value: {type(value).__name__}")


class SQLWriter:
    """Record the original generator's INSERTs without any database driver.

    IDs are explicit integers assigned offline, beginning at 1 per table.
    Import into empty tables; synchronize sequences before subsequent default-ID inserts.
    Only the fixed queries used by populate() are accepted.
    """
    def __init__(self):
        self.statements = []
        self.variables = []
        self.counts = {}
        self.buyers = []
        self.result = []
        self.explicit_ids = {}

    def execute(self, sql, params=()):
        sql = " ".join(sql.split())
        count = re.fullmatch(r"SELECT count\(\*\) FROM (\w+)", sql)
        if count:
            self.result = [(self.counts.get(count[1], 0),)]
            return
        if sql == "SELECT buyer_id, full_name, phone FROM buyer":
            self.result = list(self.buyers)
            return
        match = re.fullmatch(
            r"INSERT INTO (\w+) \(([^)]+)\) VALUES \((.*)\)"
            r"(?: RETURNING (\w+))?;?", sql,
        )
        if not match:
            raise ValueError(f"Unsupported query: {sql}")
        table, column_list, values, returning = match.groups()
        columns = [column.strip() for column in column_list.split(",")]
        identity = IDENTITY_COLUMNS.get(table)
        if returning and returning != identity:
            raise ValueError(f"Unexpected RETURNING column: {table}.{returning}")
        parts = values.split("%s")
        if len(parts) != len(params) + 1:
            raise ValueError("Placeholder count does not match parameter count")
        rendered_values = parts[0] + "".join(literal(v) + tail for v, tail in zip(params, parts[1:]))
        row_count = self.counts.get(table, 0) + 1
        self.result = []
        if returning:
            if identity in columns:
                raise ValueError("Explicit ID with RETURNING is not supported; omit the ID column")
            ref = Reference(f"v_{table}_{row_count}", row_count)
            self.variables.append(ref.name)
            columns.insert(0, identity)
            rendered_values = f"{ref.value}, {rendered_values}"
            self.result = [(ref,)]
            if table == "buyer":
                self.buyers.append((ref, params[0], params[2]))
        override = ""
        if identity in columns:
            override = " OVERRIDING SYSTEM VALUE"
            self.explicit_ids[table] = identity
        rendered = f"INSERT INTO {table} ({', '.join(columns)}){override} VALUES ({rendered_values})"
        self.counts[table] = row_count
        self.statements.append(rendered + ";")

    def fetchone(self):
        return self.result[0] if self.result else None

    def fetchall(self):
        return list(self.result)

    def write(self, path, reset=False):
        tables = ", ".join(self.counts)
        lines = [
            "-- Generated for database clothing_store, schema public. Import into empty tables.",
            "BEGIN;",
            "SET LOCAL search_path = public;",
            "SET LOCAL standard_conforming_strings = on;",
        ]
        if reset:
            lines.append(f"TRUNCATE TABLE {tables} RESTART IDENTITY;")
        lines.extend(self.statements)
        # Explicit identity values do not advance their sequences. Tables whose
        # IDs use DEFAULT already advance sequences and need no adjustment.
        for table, column in self.explicit_ids.items():
            lines.append(
                f"SELECT setval(pg_get_serial_sequence('public.{table}', '{column}'), "
                f"max({column}), true) FROM public.{table} HAVING max({column}) IS NOT NULL;"
            )
        lines.append("COMMIT;")
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


FIRST_NAMES = [
    "Александр", "Алексей", "Андрей", "Антон", "Артём", "Виктор", "Владимир",
    "Даниил", "Денис", "Дмитрий", "Иван", "Илья", "Кирилл", "Максим", "Михаил",
    "Никита", "Олег", "Павел", "Роман", "Сергей", "Тимур", "Юрий",
    "Алина", "Анна", "Дарья", "Екатерина", "Елена", "Ирина", "Мария", "Полина", "София",
]
LAST_NAMES = [
    "Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", "Соколов",
    "Михайлов", "Новиков", "Фёдоров", "Морозов", "Волков", "Алексеев", "Лебедев",
    "Семёнов", "Егоров", "Павлов", "Козлов", "Степанов", "Николаев", "Орлова", "Крылова",
]
PATRONYMICS = [
    "Александрович", "Алексеевич", "Андреевич", "Владимирович", "Дмитриевич",
    "Иванович", "Михайлович", "Николаевич", "Сергеевич", "Викторович",
    "Александровна", "Алексеевна", "Андреевна", "Владимировна", "Дмитриевна",
    "Ивановна", "Михайловна", "Николаевна", "Сергеевна", "Викторовна",
]
STREETS = ["Центральная", "Лесная", "Садовая", "Молодёжная", "Школьная", "Новая", "Советская", "Зелёная"]
CITIES = ["Казань", "Самара", "Пермь", "Тула", "Томск", "Омск", "Рязань", "Киров"]
BRANDS = ["North Line", "Urban Wear", "Cotton Way", "Basic Form", "Vento", "ModeLab", "Daily Fit"]
COLORS = ["чёрный", "белый", "синий", "серый", "красный", "зелёный", "бежевый", "коричневый"]
SIZES = ["XS", "S", "M", "L", "XL", "XXL", "42", "44", "46", "48", "50"]
JOB_TITLES = ["Продавец-консультант", "Кассир", "Администратор магазина", "Кладовщик", "Менеджер", "Старший продавец"]
JOB_DUTIES = [
    "Обслуживание покупателей и помощь с выбором товаров.",
    "Работа с кассой, оформление продаж и возвратов.",
    "Организация работы смены и контроль торгового зала.",
    "Приёмка, учёт и размещение товаров на складе.",
    "Контроль товарных остатков и подготовка отчётности.",
]
RETURN_REASONS = [
    ("wrong_size", False),
    ("customer_choice", False),
    ("wrong_item", True),
    ("defect", True),
    ("damaged_packaging", True),
    ("quality_issue", True),
    ("other", False),
]


def money(rng: random.Random, low: int, high: int) -> Decimal:
    cents = rng.randint(low * 100, high * 100)
    return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))


def person_name(rng: random.Random) -> str:
    return f"{rng.choice(LAST_NAMES)} {rng.choice(FIRST_NAMES)} {rng.choice(PATRONYMICS)}"


def random_past_timestamp(rng: random.Random, days_back: int = 180) -> datetime:
    now = REFERENCE_TIME
    return now - timedelta(days=rng.randint(0, days_back), hours=rng.randint(0, 23), minutes=rng.randint(0, 59))


def insert_id(cur: Any, sql: str, params: tuple[Any, ...]) -> int:
    cur.execute(sql, params)
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("INSERT ... RETURNING did not return an ID")
    return row[0]


def populate(cur: Any, rng: random.Random, scale: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    today = REFERENCE_TIME.date()
    now = REFERENCE_TIME
    shop_ids: list[int] = []
    for i in range(1, 4 * scale + 1):
        city = CITIES[(i - 1) % len(CITIES)]
        address = f"г. {city}, ул. {STREETS[(i - 1) % len(STREETS)]}, д. {10 + i}"
        shop_ids.append(insert_id(cur, """
            INSERT INTO shop (address, cash_registers, open_time, close_time)
            VALUES (%s, %s, %s, %s) RETURNING shop_id
        """, (address, rng.randint(1, 5), time(9, 0), time(21, 0))))
    counts["shop"] = len(shop_ids)
    employee_ids: list[int] = []
    for i in range(1, 16 * scale + 1):
        employee_ids.append(insert_id(cur, """
            INSERT INTO employee (full_name, passport, registration, birth_date, phone, education)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING employee_id
        """, (
            person_name(rng),
            str(4500000000 + i),
            f"г. {rng.choice(CITIES)}, ул. {rng.choice(STREETS)}, д. {rng.randint(1, 150)}",
            date(rng.randint(1970, 2003), rng.randint(1, 12), rng.randint(1, 28)),
            f"+7999{i:07d}",
            rng.choice(["Среднее", "Среднее специальное", "Высшее", "Неоконченное высшее"]),
        )))
    counts["employee"] = len(employee_ids)
    job_ids: list[int] = []
    for i in range(1, 6 * scale + 1):
        base = JOB_TITLES[(i - 1) % len(JOB_TITLES)]
        job_ids.append(insert_id(cur, """
            INSERT INTO job (title, description, duties)
            VALUES (%s, %s, %s) RETURNING job_id
        """, (f"{base} {i}", f"Должность: {base.lower()}.", rng.choice(JOB_DUTIES))))
    counts["job"] = len(job_ids)
    supplier_ids: list[int] = []
    for i in range(1, 8 * scale + 1):
        supplier_ids.append(insert_id(cur, """
            INSERT INTO supplier (name_, description, address, supplier_type)
            VALUES (%s, %s, %s, %s) RETURNING supplier_id
        """, (
            f"Поставщик одежды {i}",
            rng.choice(["Поставка повседневной одежды", "Оптовые поставки текстиля", "Поставка сезонных коллекций", None]),
            f"г. {rng.choice(CITIES)}, ул. {rng.choice(STREETS)}, д. {rng.randint(1, 150)}",
            rng.choice(["legal", "sole_prop", "individual"]),
        )))
    counts["supplier"] = len(supplier_ids)
    buyer_ids: list[int] = []
    for i in range(1, 40 * scale + 1):
        buyer_ids.append(insert_id(cur, """
            INSERT INTO buyer (full_name, email, phone, birth_date)
            VALUES (%s, %s, %s, %s) RETURNING buyer_id
        """, (
            person_name(rng),
            f"buyer{i:06d}@example.test",
            f"+7888{i:07d}",
            date(rng.randint(1945, 2007), rng.randint(1, 12), rng.randint(1, 28)),
        )))
    counts["buyer"] = len(buyer_ids)
    card_count = 0
    for buyer_id in buyer_ids:
        if rng.random() < 0.60:
            cur.execute("""
                INSERT INTO discount_card (buyer_id, discount_percent, registered_at)
                VALUES (%s, %s, %s)
            """, (buyer_id, rng.choice([3, 5, 7, 10, 15]), random_past_timestamp(rng, 900)))
            card_count += 1
    counts["discount_card"] = card_count
    reason_ids: list[int] = []
    for tag, shop_fault in RETURN_REASONS:
        reason_ids.append(insert_id(cur, """
            INSERT INTO return_reason (tag, is_shop_fault)
            VALUES (%s, %s) RETURNING reason_id
        """, (tag, shop_fault)))
    counts["return_reason"] = len(reason_ids)
    contract_ids: list[int] = []
    contract_by_worker: dict[int, dict[str, Any]] = {}
    contract_rows: list[dict[str, Any]] = []
    for worker_id in employee_ids:
        admin_choices = [eid for eid in employee_ids if eid != worker_id]
        start_date = today - timedelta(days=rng.randint(60, 1600))
        elapsed = (today - start_date).days
        end_date = None
        if elapsed >= 60 and rng.random() < 0.18:
            end_date = start_date + timedelta(days=rng.randint(30, elapsed))
        salary = money(rng, 35000, 95000)
        hourly_rate = money(rng, 200, 700)
        contract_id = insert_id(cur, """
            INSERT INTO contract (worker_id, job_id, shop_id, admin_id, start_date, end_date, salary, hour_)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING contract_id
        """, (
            worker_id, rng.choice(job_ids), rng.choice(shop_ids), rng.choice(admin_choices),
            start_date, end_date, salary, hourly_rate,
        ))
        row = {"contract_id": contract_id, "worker_id": worker_id, "salary": salary,
               "start_date": start_date, "end_date": end_date}
        contract_ids.append(contract_id)
        contract_rows.append(row)
        contract_by_worker[worker_id] = row
    counts["contract"] = len(contract_ids)
    schedule_count = 0
    for contract in contract_rows:
        anchor = contract["end_date"] or today
        monday = anchor - timedelta(days=anchor.weekday())
        for offset in range(7):
            work_date = monday + timedelta(days=offset)
            if work_date < contract["start_date"] or (contract["end_date"] and work_date > contract["end_date"]):
                continue
            working = work_date.weekday() < 5
            if working:
                start_t = time(9, 0)
                end_t = time(18, 0)
                lunch_start = time(13, 0) if rng.random() < 0.85 else None
                lunch_end = time(14, 0) if lunch_start is not None else None
            else:
                start_t = end_t = lunch_start = lunch_end = None
            cur.execute("""
                INSERT INTO schedule (contract_id, is_working_day, start_time, end_time,
                                      lunch_start, lunch_end, work_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (contract["contract_id"], working, start_t, end_t, lunch_start, lunch_end, work_date))
            schedule_count += 1
    counts["schedule"] = schedule_count
    room_count = 0
    for shop_id in shop_ids:
        for _ in range(rng.randint(2, 4)):
            cur.execute("""
                INSERT INTO room (shop_id, room_type, area, rent_cost, amount)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                shop_id, rng.choice(["hall", "warehouse"]),
                round(rng.uniform(12.0, 220.0), 2), money(rng, 10000, 80000), rng.randint(0, 50),
            ))
            room_count += 1
    counts["room"] = room_count
    garment_ids: list[int] = []
    garment_price: dict[int, Decimal] = {}
    for i in range(1, 40 * scale + 1):
        buy_price = money(rng, 300, 5000)
        retail_price = (buy_price * Decimal(str(rng.uniform(1.25, 2.2)))).quantize(Decimal("0.01"))
        garment_id = insert_id(cur, """
            INSERT INTO garment (brand, color, size_, kind, buy_price, retail_price, is_designer)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING garment_id
        """, (
            rng.choice(BRANDS), rng.choice(COLORS), rng.choice(SIZES),
            rng.choice(["man", "woman", "kid", "usex"]), buy_price, retail_price, rng.random() < 0.12,
        ))
        garment_ids.append(garment_id)
        garment_price[garment_id] = retail_price
    counts["garment"] = len(garment_ids)
    kit_ids: list[int] = []
    kit_price: dict[int, Decimal] = {}
    kit_count = 8 * scale
    for i in range(1, kit_count + 1):
        price = money(rng, 1000, 12000)
        kit_id = insert_id(cur, """
            INSERT INTO kit (name_, retail_price) VALUES (%s, %s) RETURNING kit_id
        """, (f"Комплект одежды {i}", price))
        kit_ids.append(kit_id)
        kit_price[kit_id] = price
        for garment_id in rng.sample(garment_ids, k=min(len(garment_ids), rng.randint(2, 4))):
            cur.execute("""
                INSERT INTO kit_item (garment_id, kit_id, amount) VALUES (%s, %s, %s)
            """, (garment_id, kit_id, rng.randint(1, 3)))
    counts["kit"] = len(kit_ids)
    counts["kit_item"] = kit_count * 3  # approximate; exact count is accumulated below
    cur.execute("SELECT count(*) FROM kit_item")
    counts["kit_item"] = int(cur.fetchone()[0])

    # 13. Sale items: each row represents exactly one garment OR one kit.
    sale_item_ids: list[int] = []
    sale_item_price: dict[int, Decimal] = {}
    for garment_id in garment_ids:
        sid = insert_id(cur, """
            INSERT INTO sale_item (garment_id, kit_id) VALUES (%s, NULL) RETURNING sale_item_id
        """, (garment_id,))
        sale_item_ids.append(sid)
        sale_item_price[sid] = garment_price[garment_id]
    for kit_id in kit_ids:
        sid = insert_id(cur, """
            INSERT INTO sale_item (garment_id, kit_id) VALUES (NULL, %s) RETURNING sale_item_id
        """, (kit_id,))
        sale_item_ids.append(sid)
        sale_item_price[sid] = kit_price[kit_id]
    counts["sale_item"] = len(sale_item_ids)
    supply_count = 12 * scale
    for _ in range(supply_count):
        ordered_at = random_past_timestamp(rng, 240)
        delivered_at = ordered_at + timedelta(hours=rng.randint(2, 96)) if rng.random() < 0.82 else None
        chosen_garments = rng.sample(garment_ids, k=rng.randint(1, min(5, len(garment_ids))))
        lines: list[tuple[int, int, Decimal]] = []
        total = Decimal("0.00")
        for garment_id in chosen_garments:
            amount = rng.randint(2, 30)
            unit_price = money(rng, 250, 4000)
            lines.append((garment_id, amount, unit_price))
            total += unit_price * amount
        supply_id = insert_id(cur, """
            INSERT INTO supply (supplier_id, shop_id, ordered_at, delivered_at, total_cost)
            VALUES (%s, %s, %s, %s, %s) RETURNING supply_id
        """, (rng.choice(supplier_ids), rng.choice(shop_ids), ordered_at, delivered_at, total))
        for garment_id, amount, unit_price in lines:
            cur.execute("""
                INSERT INTO supply_item (supply_id, garment_id, amount, unit_price)
                VALUES (%s, %s, %s, %s)
            """, (supply_id, garment_id, amount, unit_price))
    counts["supply"] = supply_count
    cur.execute("SELECT count(*) FROM supply_item")
    counts["supply_item"] = int(cur.fetchone()[0])
    cheque_rows: list[dict[str, Any]] = []
    cheque_lines_by_id: dict[int, list[dict[str, Any]]] = {}
    cheque_count = 40 * scale
    for _ in range(cheque_count):
        buyer_id = rng.choice(buyer_ids) if rng.random() < 0.75 else None
        discount = rng.choice([0, 0, 0, 5, 10, 15]) if buyer_id is not None else 0
        created_at = random_past_timestamp(rng, 120)
        cheque_id = insert_id(cur, """
            INSERT INTO cheque (shop_id, seller_id, buyer_id, discount_percent, created_at)
            VALUES (%s, %s, %s, %s, %s) RETURNING cheque_id
        """, (rng.choice(shop_ids), rng.choice(employee_ids), buyer_id, discount, created_at))
        cheque_rows.append({"cheque_id": cheque_id, "buyer_id": buyer_id, "created_at": created_at})
        lines: list[dict[str, Any]] = []
        selected_sales = rng.sample(sale_item_ids, k=rng.randint(1, min(4, len(sale_item_ids))))
        for sale_item_id in selected_sales:
            amount = rng.randint(1, 4)
            unit_price = sale_item_price[sale_item_id]
            cheque_item_id = insert_id(cur, """
                INSERT INTO cheque_item (cheque_id, sale_item_id, amount, unit_price)
                VALUES (%s, %s, %s, %s) RETURNING cheque_item_id
            """, (cheque_id, sale_item_id, amount, unit_price))
            lines.append({"cheque_item_id": cheque_item_id, "sale_item_id": sale_item_id, "amount": amount})
        cheque_lines_by_id[cheque_id] = lines
    counts["cheque"] = len(cheque_rows)
    cur.execute("SELECT count(*) FROM cheque_item")
    counts["cheque_item"] = int(cur.fetchone()[0])
    order_rows: list[dict[str, Any]] = []
    order_lines_by_id: dict[int, list[dict[str, Any]]] = {}
    order_count = 35 * scale
    for _ in range(order_count):
        buyer_id = rng.choice(buyer_ids) if rng.random() < 0.80 else None
        created_at = random_past_timestamp(rng, 100)
        fulfillment = rng.choice(["delivery", "pickup"])
        status = rng.choices(["new", "postpone", "cancel", "done"], weights=[15, 10, 10, 65], k=1)[0]
        order_id = insert_id(cur, """
            INSERT INTO customer_order (shop_id, seller_id, buyer_id, fulfil_shop_id, created_at,
                                        fulfillment, status, comment_, channel)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING order_id
        """, (
            rng.choice(shop_ids), rng.choice(employee_ids), buyer_id, rng.choice(shop_ids), created_at,
            fulfillment, status, rng.choice([None, "Позвонить перед выдачей", "Уточнить размер", "Упаковать отдельно"]),
            rng.choice(["phone", "internet"]),
        ))
        order_rows.append({"order_id": order_id, "buyer_id": buyer_id, "created_at": created_at,
                           "fulfillment": fulfillment, "status": status})
        lines: list[dict[str, Any]] = []
        selected_sales = rng.sample(sale_item_ids, k=rng.randint(1, min(4, len(sale_item_ids))))
        for sale_item_id in selected_sales:
            amount = rng.randint(1, 4)
            unit_price = sale_item_price[sale_item_id]
            order_item_id = insert_id(cur, """
                INSERT INTO order_item (order_id, sale_item_id, amount, unit_price)
                VALUES (%s, %s, %s, %s) RETURNING order_item_id
            """, (order_id, sale_item_id, amount, unit_price))
            lines.append({"order_item_id": order_item_id, "sale_item_id": sale_item_id, "amount": amount})
        order_lines_by_id[order_id] = lines
    counts["customer_order"] = len(order_rows)
    cur.execute("SELECT count(*) FROM order_item")
    counts["order_item"] = int(cur.fetchone()[0])
    delivery_note_rows: list[dict[str, Any]] = []
    delivery_item_count = 0
    cur.execute("SELECT buyer_id, full_name, phone FROM buyer")
    buyer_contact = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
    for order in order_rows:
        if order["fulfillment"] != "delivery" or order["status"] == "cancel" or rng.random() > 0.82:
            continue
        planned_at = order["created_at"] + timedelta(hours=rng.randint(2, 72))
        delivered_at = (
            planned_at + timedelta(hours=rng.randint(1, 8))
            if planned_at <= now and rng.random() < 0.80
            else None
        )
        courier_id = rng.choice(employee_ids)
        buyer_id = order["buyer_id"]
        if buyer_id is not None:
            customer_name, customer_phone = buyer_contact[buyer_id]
        else:
            customer_name, customer_phone = person_name(rng), f"+7777{rng.randint(10000000, 99999999)}"
        to_shop_id = rng.choice(shop_ids) if rng.random() < 0.12 else None
        is_negative = delivered_at is not None and rng.random() < 0.08
        note_id = insert_id(cur, """
            INSERT INTO delivery_note (order_id, courier_id, to_shop_id, customer_name, customer_phone,
                                       address, planned_at, delivered_at, customer_signature, review,
                                       delivery_fee, is_negative)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING delivery_note_id
        """, (
            order["order_id"], courier_id, to_shop_id, customer_name, customer_phone,
            f"г. {rng.choice(CITIES)}, ул. {rng.choice(STREETS)}, д. {rng.randint(1, 150)}",
            planned_at, delivered_at,
            "Подпись получателя" if delivered_at is not None else None,
            ("Всё хорошо" if not is_negative else "Проблема с доставкой") if delivered_at is not None else None,
            money(rng, 150, 900), is_negative,
        ))
        delivery_note_rows.append({"delivery_note_id": note_id, "order_id": order["order_id"],
                                   "courier_id": courier_id, "delivered_at": delivered_at})
        order_lines = order_lines_by_id[order["order_id"]]
        selected_lines = rng.sample(order_lines, k=rng.randint(1, len(order_lines)))
        for line in selected_lines:
            cur.execute("""
                INSERT INTO delivery_item (note_id, order_item_id, amount, status)
                VALUES (%s, %s, %s, %s)
            """, (note_id, line["order_item_id"], rng.randint(1, line["amount"]),
                  rng.choices(["accepted", "refused"], weights=[90, 10], k=1)[0]))
            delivery_item_count += 1
    counts["delivery_note"] = len(delivery_note_rows)
    counts["delivery_item"] = delivery_item_count
    first_of_month = today.replace(day=1)
    payment_count = 0
    for contract in contract_rows:
        if contract["end_date"] is None:
            paid_day = first_of_month + timedelta(days=rng.randint(0, (today - first_of_month).days))
        else:
            span = (contract["end_date"] - contract["start_date"]).days
            paid_day = contract["start_date"] + timedelta(days=rng.randint(0, span))
        paid_at = datetime.combine(paid_day, time(12, 0), tzinfo=timezone.utc)
        cur.execute("""
            INSERT INTO payment_order (contract_id, delivery_note_id, amount, paid_at, reason, period_month)
            VALUES (%s, NULL, %s, %s, 'salary', %s)
        """, (contract["contract_id"], contract["salary"], paid_at, paid_day.replace(day=1)))
        payment_count += 1
        if contract["end_date"] is None and rng.random() < 0.15:
            bonus_paid_at = now - timedelta(days=rng.randint(0, 90))
            cur.execute("""
                INSERT INTO payment_order (contract_id, delivery_note_id, amount, paid_at, reason, period_month)
                VALUES (%s, NULL, %s, %s, 'bonus', NULL)
            """, (contract["contract_id"], money(rng, 1000, 12000), bonus_paid_at))
            payment_count += 1
    for note in delivery_note_rows:
        if note["delivered_at"] is None:
            continue
        courier_contract = contract_by_worker[note["courier_id"]]
        cur.execute("""
            INSERT INTO payment_order (contract_id, delivery_note_id, amount, paid_at, reason, period_month)
            VALUES (%s, %s, %s, %s, 'delivery', NULL)
        """, (courier_contract["contract_id"], note["delivery_note_id"], money(rng, 200, 1200),
              note["delivered_at"]))
        payment_count += 1
    counts["payment_order"] = payment_count
    valid_cheques = [c for c in cheque_rows if cheque_lines_by_id[c["cheque_id"]]]
    valid_orders = [o for o in order_rows if order_lines_by_id[o["order_id"]]]
    return_count = 10 * scale
    return_item_count = 0
    for _ in range(return_count):
        use_cheque = bool(valid_cheques) and (not valid_orders or rng.random() < 0.50)
        reason_id = rng.choice(reason_ids)
        employee_id = rng.choice(employee_ids)
        if use_cheque:
            cheque = rng.choice(valid_cheques)
            valid_cheques.remove(cheque)
            return_id = insert_id(cur, """
                INSERT INTO product_return (cheque_id, order_id, reason_id, employee_id,
                                            returned_at, delivery_fee_refunded)
                VALUES (%s, NULL, %s, %s, %s, FALSE) RETURNING return_id
            """, (cheque["cheque_id"], reason_id, employee_id, cheque["created_at"] + (REFERENCE_TIME - cheque["created_at"]) * rng.random()))
            source_lines = cheque_lines_by_id[cheque["cheque_id"]]
            selected = rng.sample(source_lines, k=rng.randint(1, len(source_lines)))
            for source_line in selected:
                cur.execute("""
                    INSERT INTO return_item (return_id, cheque_item_id, order_item_id, amount, destination)
                    VALUES (%s, %s, NULL, %s, %s)
                """, (return_id, source_line["cheque_item_id"], rng.randint(1, source_line["amount"]),
                      rng.choice(["stock", "written_off"])))
                return_item_count += 1
        else:
            order = rng.choice(valid_orders)
            valid_orders.remove(order)
            orders_with_notes = {note["order_id"] for note in delivery_note_rows}
            refund_fee = (
                order["fulfillment"] == "delivery"
                and order["order_id"] in orders_with_notes
                and rng.random() < 0.20
            )
            return_id = insert_id(cur, """
                INSERT INTO product_return (cheque_id, order_id, reason_id, employee_id,
                                            returned_at, delivery_fee_refunded)
                VALUES (NULL, %s, %s, %s, %s, %s) RETURNING return_id
            """, (order["order_id"], reason_id, employee_id, order["created_at"] + (REFERENCE_TIME - order["created_at"]) * rng.random(), refund_fee))
            source_lines = order_lines_by_id[order["order_id"]]
            selected = rng.sample(source_lines, k=rng.randint(1, len(source_lines)))
            for source_line in selected:
                cur.execute("""
                    INSERT INTO return_item (return_id, cheque_item_id, order_item_id, amount, destination)
                    VALUES (%s, NULL, %s, %s, %s)
                """, (return_id, source_line["order_item_id"], rng.randint(1, source_line["amount"]),
                      rng.choice(["stock", "written_off"])))
                return_item_count += 1
    counts["product_return"] = return_count
    counts["return_item"] = return_item_count

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate clothing_store INSERTs offline; no database connection.")
    parser.add_argument("--output", "-o", type=Path, default=Path("clothing_store_data.sql"))
    parser.add_argument("--scale", type=int, default=1, help="Positive integer data multiplier")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reset", action="store_true", help="Include TRUNCATE RESTART IDENTITY in the SQL file")
    args = parser.parse_args()
    if args.scale < 1:
        parser.error("--scale must be at least 1")
    try:
        writer = SQLWriter()
        counts = populate(writer, random.Random(args.seed), args.scale)
        if counts != writer.counts:
            raise RuntimeError("Generated row counts do not match recorded INSERTs")
        writer.write(args.output, reset=args.reset)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Generation failed: {exc}", file=sys.stderr)
        return 1
    print(f"SQL file: {args.output.resolve()}")
    for table, count in counts.items():
        print(f"  {table:20s} {count:>6}")
    print(f"Total rows: {sum(counts.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
