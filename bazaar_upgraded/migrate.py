"""
bazaar/migrate.py

Database migration helper for Bazaar@IITGN.
Adds any missing columns to an existing database without losing data.

Run once after upgrading:
    python migrate.py

This is safe to re-run — it skips columns that already exist.
"""

import os
from dotenv import load_dotenv
from urllib.parse import quote_plus
import pymysql

load_dotenv()

DB_USER     = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_HOSTING = os.environ.get('DB_HOSTING')  # Use DB_HOSTING to avoid conflicts with app.py
DB_PORT     = int(os.environ.get('DB_PORT'))
DB_NAME     = os.environ.get('DB_NAME')


def get_existing_columns(cursor, table):
    cursor.execute(f"SHOW COLUMNS FROM `{table}`")
    return {row['Field'] for row in cursor.fetchall()}


def add_column_if_missing(cursor, table, column, definition):
    existing = get_existing_columns(cursor, table)
    if column not in existing:
        cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")
        print(f"  ✅ Added `{column}` to `{table}`")
    else:
        print(f"  ⏭  `{column}` already exists in `{table}`")


def run_migrations():
    conn = pymysql.connect(
        host=DB_HOSTING, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with conn.cursor() as cursor:
            print("\n── Members table ──────────────────────────────────────")
            # Bug fix: ensure hostel + wing exist (they should, but guarantee it)
            add_column_if_missing(cursor, 'Members', 'hostel', "VARCHAR(100) DEFAULT NULL")
            add_column_if_missing(cursor, 'Members', 'wing',   "VARCHAR(50) DEFAULT NULL")
            add_column_if_missing(cursor, 'Members', 'karma_score', "INT NOT NULL DEFAULT 0")

            print("\n── Products table ─────────────────────────────────────")
            add_column_if_missing(cursor, 'Products', 'tags',         "VARCHAR(500) DEFAULT NULL")
            add_column_if_missing(cursor, 'Products', 'is_urgent',    "TINYINT(1) NOT NULL DEFAULT 0")
            add_column_if_missing(cursor, 'Products', 'pickup_point', "VARCHAR(200) DEFAULT NULL")
            add_column_if_missing(cursor, 'Products', 'status',       "VARCHAR(20) NOT NULL DEFAULT 'available'")

            print("\n── TransactionHistory table ───────────────────────────")
            # Verified Handshake System columns
            add_column_if_missing(cursor, 'TransactionHistory', 'buyer_confirmed',
                                  "TINYINT(1) NOT NULL DEFAULT 0 AFTER status")
            add_column_if_missing(cursor, 'TransactionHistory', 'seller_confirmed',
                                  "TINYINT(1) NOT NULL DEFAULT 0 AFTER buyer_confirmed")
            add_column_if_missing(cursor, 'TransactionHistory', 'pickup_point',
                                  "VARCHAR(200) DEFAULT NULL")

            conn.commit()
            print("\n✅ Migration complete!\n")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}\n")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run_migrations()
