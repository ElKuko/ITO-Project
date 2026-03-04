"""Seed script for Ito SKUs - Productos Refrigerados"""

from backend.database import SessionLocal
from backend.models import SKU

# Productos Refrigerados data
PRODUCTOS_REFRIGERADOS = [
    {"upc": "8-50049-00501-2", "code": "358010", "name": "Recaito Original", "name_en": "Natural Seasoning Original", "pack": 12, "size": "32 oz"},
    {"upc": "8-50049-00529-6", "code": "358012", "name": "Recaito con Albahaca", "name_en": "Natural Seasoning with Basil", "pack": 12, "size": "32 oz"},
    {"upc": "8-50049-00523-4", "code": "358025", "name": "Recaito Sabor a Pollo y Curcuma", "name_en": "Natural Seasoning with Chicken Flavor & Turmeric", "pack": 12, "size": "32 oz"},
    {"upc": "8-50049-00503-6", "code": "358014", "name": "Sofrito con Sazón y Tomate", "name_en": "Natural Seasoning with Seasoning & Tomato", "pack": 12, "size": "32 oz"},
    {"upc": "8-50049-00518-0", "code": "358013", "name": "Sofrito con Sazón y Achiote", "name_en": "Natural Seasoning with Seasoning & Annatto", "pack": 12, "size": "32 oz"},
    {"upc": "8-50049-00508-1", "code": "358018", "name": "Ajo Molido", "name_en": "Ground Garlic", "pack": 12, "size": "32 oz"},
    {"upc": "8-50049-00510-4", "code": "358030", "name": "Ajo con Albahaca", "name_en": "Garlic with Basil", "pack": 12, "size": "32 oz"},
    {"upc": "8-50049-00516-6", "code": "358022", "name": "Ajo con Cilantro", "name_en": "Garlic with Cilantro", "pack": 12, "size": "32 oz"},
    {"upc": "8-50049-00566-1", "code": "358032", "name": "Ajo Picado", "name_en": "Chopped Garlic", "pack": 12, "size": "32 oz"},
    {"upc": "8-50049-00500-5", "code": "358007", "name": "Recaito Original", "name_en": "Natural Seasoning Original", "pack": 24, "size": "12 oz"},
    {"upc": "8-50049-00504-3", "code": "358009", "name": "Recaito con Albahaca", "name_en": "Natural Seasoning with Basil", "pack": 24, "size": "12 oz"},
    {"upc": "8-50049-00522-7", "code": "358024", "name": "Recaito Sabor a Pollo y Curcuma", "name_en": "Natural Seasoning with Chicken Flavor & Turmeric", "pack": 24, "size": "12 oz"},
    {"upc": "8-50049-00502-9", "code": "358008", "name": "Sofrito con Sazón y Tomate", "name_en": "Natural Seasoning with Seasoning & Tomato", "pack": 24, "size": "12 oz"},
    {"upc": "8-50049-00517-3", "code": "358002", "name": "Sofrito con Sazón y Achiote", "name_en": "Natural Seasoning with Seasoning & Annatto", "pack": 24, "size": "12 oz"},
    {"upc": "8-50049-00506-7", "code": "358015", "name": "Ajo Molido", "name_en": "Ground Garlic", "pack": 24, "size": "8 oz"},
    {"upc": "8-50049-00509-8", "code": "358016", "name": "Ajo con Albahaca", "name_en": "Garlic with Basil", "pack": 24, "size": "8 oz"},
    {"upc": "8-50049-00511-1", "code": "358017", "name": "Ajo con Cilantro", "name_en": "Garlic with Cilantro", "pack": 24, "size": "8 oz"},
    {"upc": "8-50049-00520-3", "code": "358026", "name": "Ajo Picado", "name_en": "Chopped Garlic", "pack": 24, "size": "8 oz"},
    {"upc": "8-50049-00526-5", "code": "358035", "name": "Squeeze! Ajo Molido", "name_en": "Squeeze! Ground Garlic", "pack": 12, "size": "12 oz"},
    {"upc": "8-50049-00525-8", "code": "358036", "name": "Squeeze! Adobo de Ajo", "name_en": "Squeeze! Garlic Seasoning", "pack": 12, "size": "12 oz"},
    {"upc": "8-50049-00530-2", "code": "358033", "name": "Recaito Original (Cash & Carry)", "name_en": "Natural Seasoning Original (Cash & Carry)", "pack": 6, "size": "64 oz"},
    {"upc": "8-50049-00531-9", "code": "358037", "name": "Ajo Molido (Costco)", "name_en": "Ground Garlic (Costco)", "pack": 6, "size": "64 oz"},
    {"upc": "8-50049-00513-5", "code": "373047", "name": "Recaito Original (Sam's)", "name_en": "Natural Seasoning Original (Sam's)", "pack": 4, "size": "128 oz"},
    {"upc": "8-50049-00513-5", "code": "406055", "name": "Recaito Original (Cash & Carry)", "name_en": "Natural Seasoning Original (Cash & Carry)", "pack": 4, "size": "128 oz"},
    {"upc": "8-50049-00514-2", "code": "406056", "name": "Ajo Molido (Cash & Carry)", "name_en": "Ground Garlic (Cash & Carry)", "pack": 4, "size": "128 oz"},
    {"upc": "8-50049-00515-9", "code": "406196", "name": "Sofrito con Sazón y Tomate (Cash & Carry)", "name_en": "Natural Seasoning with Seasoning & Tomato (Cash & Carry)", "pack": 4, "size": "128 oz"},
]


def seed_refrigerados():
    db = SessionLocal()

    created = 0
    skipped = 0

    for p in PRODUCTOS_REFRIGERADOS:
        # Create full product name with size
        full_name = f"{p['name']} {p['size']}"
        barcode = p['upc'].replace("-", "")  # Remove dashes from UPC

        # Check if SKU already exists by barcode
        existing = db.query(SKU).filter(SKU.barcode == barcode).first()
        if existing:
            print(f"  Skipped (exists): {full_name}")
            skipped += 1
            continue

        sku = SKU(
            name=full_name,
            brand="Ito",
            category="Productos Refrigerados",
            barcode=barcode,
        )
        db.add(sku)
        created += 1
        print(f"  Created: {full_name}")

    db.commit()
    db.close()

    print(f"\nDone! Created: {created}, Skipped: {skipped}")


if __name__ == "__main__":
    print("Seeding Productos Refrigerados...")
    seed_refrigerados()
