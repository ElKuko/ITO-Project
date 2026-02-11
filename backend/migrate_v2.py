"""
Migration script to add gondola grouping support (Workflow v2).
Run this script once to update your existing database.

Usage: python backend/migrate_v2.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "ito.db")

def migrate():
    print(f"Migrating database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if gondola_group_id column exists
    cursor.execute("PRAGMA table_info(visit_photos)")
    columns = [col[1] for col in cursor.fetchall()]

    if "gondola_group_id" not in columns:
        print("Adding gondola_group_id column to visit_photos...")
        cursor.execute("ALTER TABLE visit_photos ADD COLUMN gondola_group_id VARCHAR(36)")
        print("  Done.")
    else:
        print("gondola_group_id column already exists.")

    # Check if photo_sku_links table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='photo_sku_links'")
    if not cursor.fetchone():
        print("Creating photo_sku_links table...")
        cursor.execute("""
            CREATE TABLE photo_sku_links (
                id INTEGER PRIMARY KEY,
                photo_id INTEGER NOT NULL,
                sku_id INTEGER NOT NULL,
                FOREIGN KEY (photo_id) REFERENCES visit_photos(id),
                FOREIGN KEY (sku_id) REFERENCES skus(id)
            )
        """)
        cursor.execute("CREATE INDEX ix_photo_sku_links_photo_id ON photo_sku_links(photo_id)")
        cursor.execute("CREATE INDEX ix_photo_sku_links_sku_id ON photo_sku_links(sku_id)")
        print("  Done.")
    else:
        print("photo_sku_links table already exists.")

    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
