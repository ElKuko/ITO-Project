"""Migration script to populate SKU sections based on category.

Maps existing categories to store sections:
- Productos Refrigerados → produce
- Productos Secos → provisiones
- Productos Congelados → congelados
"""

from backend.database import SessionLocal, engine
from backend.models import SKU, Base
from sqlalchemy import text


def migrate_sections():
    # Ensure the column exists (for SQLite, we need to handle this carefully)
    db = SessionLocal()

    try:
        # Check if column exists by trying to query it
        db.execute(text("SELECT section FROM skus LIMIT 1"))
    except Exception:
        # Column doesn't exist, add it
        print("Adding 'section' column to skus table...")
        db.execute(text("ALTER TABLE skus ADD COLUMN section VARCHAR(50)"))
        db.commit()

    # Map categories to sections
    category_to_section = {
        "Productos Refrigerados": "produce",
        "Productos Secos": "provisiones",
        "Productos Congelados": "congelados",
    }

    updated = 0
    skipped = 0

    skus = db.query(SKU).all()

    for sku in skus:
        if sku.section:
            print(f"  Skipped (already has section): {sku.name}")
            skipped += 1
            continue

        section = category_to_section.get(sku.category)
        if section:
            sku.section = section
            updated += 1
            print(f"  Updated: {sku.name} → {section}")
        else:
            print(f"  Skipped (unknown category '{sku.category}'): {sku.name}")
            skipped += 1

    db.commit()
    db.close()

    print(f"\nMigration complete! Updated: {updated}, Skipped: {skipped}")


if __name__ == "__main__":
    print("Migrating SKU sections...")
    print("=" * 50)
    migrate_sections()
