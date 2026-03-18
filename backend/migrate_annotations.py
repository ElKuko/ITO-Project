"""Migration script to add annotation support to the database."""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "ito.db")


def migrate():
    """Add annotation columns and table to database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if image_annotations table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='image_annotations'
    """)
    if not cursor.fetchone():
        print("Creating image_annotations table...")
        cursor.execute("""
            CREATE TABLE image_annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_id INTEGER NOT NULL,
                visit_id INTEGER NOT NULL,
                photo_type VARCHAR(30) NOT NULL,
                gondola_group_id VARCHAR(36),
                annotation_data TEXT NOT NULL,
                preview_path VARCHAR(500),
                created_by INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (photo_id) REFERENCES visit_photos(id),
                FOREIGN KEY (visit_id) REFERENCES store_visits(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)
        cursor.execute("CREATE INDEX ix_image_annotations_photo_id ON image_annotations(photo_id)")
        cursor.execute("CREATE INDEX ix_image_annotations_visit_id ON image_annotations(visit_id)")
        print("Created image_annotations table.")

    # Check if chat_messages has ref_annotation_id column
    cursor.execute("PRAGMA table_info(chat_messages)")
    columns = [col[1] for col in cursor.fetchall()]

    if "ref_annotation_id" not in columns:
        print("Adding ref_annotation_id column to chat_messages...")
        cursor.execute("ALTER TABLE chat_messages ADD COLUMN ref_annotation_id INTEGER")
        print("Added ref_annotation_id column.")

    if "ref_annotation_preview_url" not in columns:
        print("Adding ref_annotation_preview_url column to chat_messages...")
        cursor.execute("ALTER TABLE chat_messages ADD COLUMN ref_annotation_preview_url VARCHAR(500)")
        print("Added ref_annotation_preview_url column.")

    conn.commit()
    conn.close()
    print("Migration complete!")


if __name__ == "__main__":
    migrate()
