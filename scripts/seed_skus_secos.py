"""Seed script for Ito SKUs - Productos Secos (Dry)"""

from backend.database import SessionLocal
from backend.models import SKU

# Productos Secos data
PRODUCTOS_SECOS = [
    {"upc": "8-50049-00619-4", "code": "000000", "name": "Adobo con Pimienta", "name_en": "All Purpose Seasoning with Pepper", "pack": 4, "size": "7.5 lb"},
    {"upc": "8-50049-00620-0", "code": "000000", "name": "Adobo sin Pimienta", "name_en": "All Purpose Seasoning without Pepper", "pack": 4, "size": "7.5 lb"},
    {"upc": "8-50049-00638-5", "code": "000000", "name": "Adobo con Sazón con Pimienta", "name_en": "All Purpose Seasoning with Annatto & Pepper", "pack": 4, "size": "7.5 lb"},
    {"upc": "8-50049-00639-2", "code": "000000", "name": "Adobo con Sazón sin Pimienta", "name_en": "All Purpose Seasoning with Annatto & without Pepper", "pack": 4, "size": "7.5 lb"},
    {"upc": "8-50049-00650-7", "code": "202738", "name": "Adobo con Pimienta", "name_en": "All Purpose Seasoning with Pepper", "pack": 6, "size": "3.75 lb"},
    {"upc": "8-50049-00651-4", "code": "202739", "name": "Adobo sin Pimienta", "name_en": "All Purpose Seasoning without Pepper", "pack": 6, "size": "3.75 lb"},
    {"upc": "8-50049-00652-1", "code": "000000", "name": "Adobo con Sazón con Pimienta", "name_en": "All Purpose Seasoning with Annatto & Pepper", "pack": 6, "size": "3.75 lb"},
    {"upc": "8-50049-00653-4", "code": "000000", "name": "Adobo con Sazón sin Pimienta", "name_en": "All Purpose Seasoning with Annatto & without Pepper", "pack": 6, "size": "3.75 lb"},
    {"upc": "8-50049-00634-7", "code": "202734", "name": "Adobo con Pimienta", "name_en": "All Purpose Seasoning with Pepper", "pack": 12, "size": "28 oz"},
    {"upc": "8-50049-00635-4", "code": "202735", "name": "Adobo sin Pimienta", "name_en": "All Purpose Seasoning without Pepper", "pack": 12, "size": "28 oz"},
    {"upc": "8-50049-00636-1", "code": "202736", "name": "Adobo con Sazón con Pimienta", "name_en": "All Purpose Seasoning with Annatto & Pepper", "pack": 12, "size": "28 oz"},
    {"upc": "8-50049-00637-8", "code": "202737", "name": "Adobo con Sazón sin Pimienta", "name_en": "All Purpose Seasoning with Annatto & without Pepper", "pack": 12, "size": "28 oz"},
    {"upc": "8-50049-00621-7", "code": "202730", "name": "Adobo con Pimienta", "name_en": "All Purpose Seasoning with Pepper", "pack": 24, "size": "10.5 oz"},
    {"upc": "8-50049-00622-4", "code": "202731", "name": "Adobo sin Pimienta", "name_en": "All Purpose Seasoning without Pepper", "pack": 24, "size": "10.5 oz"},
    {"upc": "8-50049-00618-7", "code": "202732", "name": "Adobo con Sazón con Pimienta", "name_en": "All Purpose Seasoning with Annatto & Pepper", "pack": 24, "size": "10.5 oz"},
    {"upc": "8-50049-00623-1", "code": "202733", "name": "Adobo con Sazón sin Pimienta", "name_en": "All Purpose Seasoning with Annatto & without Pepper", "pack": 24, "size": "10.5 oz"},
]


def seed_secos():
    db = SessionLocal()

    created = 0
    skipped = 0

    for p in PRODUCTOS_SECOS:
        # Create full product name with size
        full_name = f"{p['name']} {p['size']}"
        barcode = p['upc'].replace("-", "")  # Remove dashes from UPC

        # Check if SKU already exists by name (includes size) to avoid duplicates
        existing = db.query(SKU).filter(SKU.name == full_name, SKU.category == "Productos Secos").first()
        if existing:
            print(f"  Skipped (exists): {full_name}")
            skipped += 1
            continue

        sku = SKU(
            name=full_name,
            brand="Ito",
            category="Productos Secos",
            section="provisiones",
            barcode=barcode,
        )
        db.add(sku)
        created += 1
        print(f"  Created: {full_name}")

    db.commit()
    db.close()

    print(f"\nDone! Created: {created}, Skipped: {skipped}")


if __name__ == "__main__":
    print("Seeding Productos Secos...")
    seed_secos()
