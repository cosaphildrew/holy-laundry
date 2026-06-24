"""
Holy Laundry - Database Module
Postgres backend (works with any hosted Postgres: Supabase, Neon, Render, Railway, etc.)
Reads the connection string from the DATABASE_URL environment variable.
"""

import os
import json
from datetime import datetime
from contextlib import contextmanager

import psycopg


DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Create a free Postgres database (e.g. on Supabase or Neon) and set "
        "DATABASE_URL to its connection string before running the app."
    )

# Some hosts (Supabase, Render, etc.) require sslmode=require
if "sslmode" not in DATABASE_URL:
    DATABASE_URL += ("&" if "?" in DATABASE_URL else "?") + "sslmode=require"

print(f"[DB] Connecting to: {DATABASE_URL[:50]}...")  # Log first 50 chars (hide password)


@contextmanager
def get_conn():
    try:
        conn = psycopg.connect(DATABASE_URL)
    except psycopg.OperationalError as e:
        print(f"[DB] Connection failed: {e}")
        raise RuntimeError(f"Database connection failed: {e}") from e
    except Exception as e:
        print(f"[DB] Connection error: {e}")
        raise RuntimeError(f"Database error: {e}") from e
    
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[DB] Query failed: {e}")
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database tables and migrate schema if needed."""
    print("[DB] Initializing database...")
    try:
        with get_conn() as conn:
            c = conn.cursor()

            # Create services table with new schema
            c.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    unit TEXT NOT NULL DEFAULT 'kg',
                    price REAL NOT NULL
                )
            """)

            # Try to add unit column if it doesn't exist (migration)
            try:
                c.execute("ALTER TABLE services ADD COLUMN unit TEXT NOT NULL DEFAULT 'kg'")
                print("[DB] Added 'unit' column to services table")
            except Exception as e:
                # Column probably already exists
                print(f"[DB] Unit column exists or migration info: {str(e)[:50]}")

            c.execute("""
                CREATE TABLE IF NOT EXISTS clients (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT,
                    address TEXT,
                    created_at BIGINT
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL REFERENCES clients(id),
                    service_id INT REFERENCES services(id),
                    items TEXT,
                    drop_off_date TEXT,
                    due_date TEXT,
                    price REAL,
                    notes TEXT,
                    status TEXT,
                    created_at BIGINT
                )
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    qty REAL,
                    unit TEXT,
                    reorder REAL,
                    created_at BIGINT
                )
            """)

            # Map service names to units (for existing services or new ones)
            service_unit_map = {
                "Light": "kg",
                "Heavy": "kg",
                "Spin and Dry": "kg",
                "Extra Dry": "load",
                "Delicate (Hand Wash)": "item",
                "Delicate": "item",
                "Shoes (Handwashed-Shoe Dryer)": "pair",
                "Shoes": "pair",
                "Power Wash": "load",
                "Fabric Conditioner": "sachet",
                "Bleach Color Safe": "sachet",
                "Bleach": "sachet",
            }

            # Update units for existing services, only if they have default unit
            print("[DB] Updating service units...")
            for service_name, unit in service_unit_map.items():
                c.execute(
                    "UPDATE services SET unit = %s WHERE name = %s AND unit = 'kg'",
                    (unit, service_name)
                )

        print("[DB] Database initialized successfully")
        print("[DB] Using prices from your Neon database services table")
    except Exception as e:
        print(f"[DB] Init error: {e}")
        raise


def _gen_id():
    """Generate a simple ID based on timestamp."""
    return str(int(datetime.now().timestamp() * 1000))


# ---------------------------------------------------------------- SERVICES
def get_services():
    """Get all service types."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, unit, price FROM services ORDER BY id")
        rows = c.fetchall()
    return [
        {"id": row[0], "name": row[1], "unit": row[2], "price": row[3]}
        for row in rows
    ]


def add_service(name, unit, price):
    """Add a new service type."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO services (name, unit, price) VALUES (%s, %s, %s) RETURNING id, name, unit, price",
            (name, unit, price),
        )
        row = c.fetchone()
    return {"id": row[0], "name": row[1], "unit": row[2], "price": row[3]}


def update_service_price(service_id, price):
    """Update service price."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE services SET price = %s WHERE id = %s", (price, service_id))


# ---------------------------------------------------------------- CLIENTS
def add_client(name, phone="", address=""):
    """Add a new client."""
    client_id = _gen_id()
    now = int(datetime.now().timestamp())
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO clients (id, name, phone, address, created_at) VALUES (%s, %s, %s, %s, %s)",
            (client_id, name, phone, address, now),
        )
    return {"id": client_id, "name": name, "phone": phone, "address": address, "created_at": now}


def get_clients():
    """Get all clients."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, phone, address, created_at FROM clients ORDER BY name")
        rows = c.fetchall()
    return [
        {"id": row[0], "name": row[1], "phone": row[2], "address": row[3], "created_at": row[4]}
        for row in rows
    ]


# ---------------------------------------------------------------- ORDERS
def add_order(client_id, service_id, items, drop_off_date, due_date, price, notes):
    """Add a new order."""
    order_id = _gen_id()
    now = int(datetime.now().timestamp())
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """INSERT INTO orders
               (id, client_id, service_id, items, drop_off_date, due_date, price, notes, status, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (order_id, client_id, service_id, json.dumps(items), drop_off_date, due_date,
             price, notes, "Dropped Off", now),
        )
    return {
        "id": order_id, "client_id": client_id, "service_id": service_id, "items": items,
        "drop_off_date": drop_off_date, "due_date": due_date, "price": price, "notes": notes,
        "status": "Dropped Off", "created_at": now,
    }


def get_orders():
    """Get all orders."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, client_id, service_id, items, drop_off_date, due_date, price, notes, status, created_at
                     FROM orders ORDER BY created_at DESC""")
        rows = c.fetchall()
    orders = []
    for row in rows:
        orders.append({
            "id": row[0],
            "client_id": row[1],
            "service_id": row[2],
            "items": json.loads(row[3]) if isinstance(row[3], str) else row[3],
            "drop_off_date": row[4],
            "due_date": row[5],
            "price": float(row[6]) if row[6] else 0,
            "notes": row[7],
            "status": row[8],
            "created_at": row[9],
        })
    return orders


def update_order_status(order_id, status):
    """Update order status."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))


# ---------------------------------------------------------------- INVENTORY
def add_inventory_item(name, qty, unit, reorder):
    """Add inventory item."""
    item_id = _gen_id()
    now = int(datetime.now().timestamp())
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO inventory (id, name, qty, unit, reorder, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (item_id, name, qty, unit, reorder, now),
        )
    return {"id": item_id, "name": name, "qty": qty, "unit": unit, "reorder": reorder, "created_at": now}


def get_inventory():
    """Get all inventory items."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, qty, unit, reorder, created_at FROM inventory ORDER BY name")
        rows = c.fetchall()
    return [
        {"id": row[0], "name": row[1], "qty": float(row[2]), "unit": row[3],
         "reorder": float(row[4]), "created_at": row[5]}
        for row in rows
    ]


def set_inventory_qty(item_id, qty):
    """Update inventory quantity."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE inventory SET qty = %s WHERE id = %s", (qty, item_id))


# Initialize on import
try:
    init_db()
except Exception as e:
    print(f"[DB] Failed to initialize on import: {e}")
