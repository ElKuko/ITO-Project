"""Seed script for Ito SKUs - Productos Congelados (Frozen)"""

from backend.database import SessionLocal
from backend.models import SKU

# Productos Congelados data
PRODUCTOS_CONGELADOS = [
    {"upc": "8-50049-00533-6", "code": "373007", "name": "Tostones de Pana", "name_en": "Fried Breadfruit", "pack": 12, "size": "20 oz"},
    {"upc": "8-50049-00532-6", "code": "373008", "name": "Tostones de Pana", "name_en": "Fried Breadfruit", "pack": 10, "size": "3 lb"},
    {"upc": "8-50049-00532-6", "code": "456486", "name": "Tostones de Pana (Cash & Carry)", "name_en": "Fried Breadfruit (Cash & Carry)", "pack": 10, "size": "3 lb"},
    {"upc": "8-50049-00601-9", "code": "373043", "name": "Tostones de Pana (Sam's)", "name_en": "Fried Breadfruit (Sam's)", "pack": 8, "size": "3.5 lb"},
    {"upc": "8-50049-00656-9", "code": "373044", "name": "Tostones de Pana (Costco)", "name_en": "Fried Breadfruit (Costco)", "pack": 6, "size": "5 lb"},
    {"upc": "8-50049-00592-0", "code": "373027", "name": "Palitos de Pana", "name_en": "Breadfruit Fries", "pack": 12, "size": "20 oz"},
    {"upc": "8-50049-00593-7", "code": "373028", "name": "Palitos de Pana", "name_en": "Breadfruit Fries", "pack": 10, "size": "3 lb"},
    {"upc": "8-50049-00593-7", "code": "456994", "name": "Palitos de Pana (Cash & Carry)", "name_en": "Breadfruit Fries (Cash & Carry)", "pack": 10, "size": "3 lb"},
    {"upc": "8-50049-00614-9", "code": "373045", "name": "Palitos de Pana (Sam's)", "name_en": "Breadfruit Fries (Sam's)", "pack": 8, "size": "3.5 lb"},
    {"upc": "8-50049-00590-6", "code": "373029", "name": "Pana en Trozo", "name_en": "Breadfruit Chunks", "pack": 12, "size": "20 oz"},
    {"upc": "8-50049-00591-3", "code": "373030", "name": "Pana en Trozo", "name_en": "Breadfruit Chunks", "pack": 10, "size": "3 lb"},
    {"upc": "8-50049-00591-3", "code": "456951", "name": "Pana en Trozo (Cash & Carry)", "name_en": "Breadfruit Chunks (Cash & Carry)", "pack": 10, "size": "3 lb"},
    {"upc": "8-50049-00594-4", "code": "373031", "name": "Palitos de Batata Blanca", "name_en": "Sweet White Potato Fries", "pack": 12, "size": "20 oz"},
    {"upc": "8-50049-00595-1", "code": "373032", "name": "Palitos de Batata Blanca", "name_en": "Sweet White Potato Fries", "pack": 10, "size": "3 lb"},
    {"upc": "8-50049-00595-1", "code": "373058", "name": "Palitos de Batata Blanca (Sam's)", "name_en": "Sweet White Potato Fries (Sam's)", "pack": 9, "size": "3 lb"},
    {"upc": "8-50049-00584-5", "code": "373014", "name": "Yuca en Trozo", "name_en": "Cassava Chunks", "pack": 32, "size": "14 oz"},
    {"upc": "8-50049-00582-1", "code": "373011", "name": "Yuca en Trozo", "name_en": "Cassava Chunks", "pack": 15, "size": "2 lb"},
    {"upc": "8-50049-00583-8", "code": "373009", "name": "Yuca en Trozo", "name_en": "Cassava Chunks", "pack": 6, "size": "5 lb"},
    {"upc": "8-50049-00581-4", "code": "373015", "name": "Ñame en Trozo", "name_en": "Yam Chunks", "pack": 15, "size": "2 lb"},
    {"upc": "8-50049-00580-7", "code": "373026", "name": "Yautía en Trozo", "name_en": "Malanga Chunks", "pack": 15, "size": "2 lb"},
    {"upc": "8-50049-00586-9", "code": "373033", "name": "Sancocho", "name_en": "Vegetable Stew", "pack": 15, "size": "2 lb"},
    {"upc": "8-50049-00574-6", "code": "373036", "name": "Masa de Guineo", "name_en": "Grated Banana", "pack": 15, "size": "2 lb"},
    {"upc": "8-50049-00578-4", "code": "373037", "name": "Masa de Alcapurria", "name_en": "Grated Alcapurria", "pack": 15, "size": "2 lb"},
    {"upc": "8-50049-00576-0", "code": "373038", "name": "Masa de Pasteles", "name_en": "Grated Pasteles", "pack": 15, "size": "2 lb"},
    {"upc": "8-50049-00572-2", "code": "373040", "name": "Masa de Yuca", "name_en": "Grated Cassava", "pack": 15, "size": "2 lb"},
    {"upc": "8-50049-00570-8", "code": "373041", "name": "Masa de Yautía", "name_en": "Grated Malanga", "pack": 15, "size": "2 lb"},
    {"upc": "8-50049-00571-5", "code": "373039", "name": "Masa de Yuca", "name_en": "Grated Cassava", "pack": 6, "size": "5 lb"},
    {"upc": "8-50049-00585-2", "code": "373042", "name": "Palitos de Yuca", "name_en": "Cassava Sticks", "pack": 12, "size": "20 oz"},
    {"upc": "8-50049-00585-2", "code": "373056", "name": "Tostones de Yuca", "name_en": "Fried Cassava", "pack": 12, "size": "20 oz"},
    {"upc": "8-50049-00645-3", "code": "373052", "name": "Gandules Verdes Congelados", "name_en": "Frozen Green Pigeon Peas", "pack": 24, "size": "14 oz"},
    {"upc": "8-50049-00647-7", "code": "373053", "name": "Gandules Verdes Congelados", "name_en": "Frozen Green Pigeon Peas", "pack": 6, "size": "5 lb"},
    {"upc": "8-50049-00642-2", "code": "373046", "name": "Mezcla de Pimiento y Cebolla", "name_en": "Peppers & Onions Mix", "pack": 6, "size": "4 lb"},
    {"upc": "8-50049-00644-6", "code": "373055", "name": "Mezcla de Pimiento y Cebolla", "name_en": "Peppers & Onions Mix", "pack": 26, "size": "1 lb"},
    {"upc": "8-50049-00643-9", "code": "373057", "name": "Mezcla de Pimiento y Cebolla", "name_en": "Peppers & Onions Mix", "pack": 12, "size": "2 lb"},
]


def seed_congelados():
    db = SessionLocal()

    created = 0
    skipped = 0
    seen_barcodes = set()

    for p in PRODUCTOS_CONGELADOS:
        # Create full product name with size
        full_name = f"{p['name']} {p['size']}"
        barcode = p['upc'].replace("-", "")  # Remove dashes from UPC

        # Check by barcode (in DB or current batch) to avoid UNIQUE constraint failures
        if barcode in seen_barcodes or db.query(SKU).filter(SKU.barcode == barcode).first():
            print(f"  Skipped (exists): {full_name}")
            skipped += 1
            continue

        seen_barcodes.add(barcode)

        sku = SKU(
            name=full_name,
            brand="Ito",
            category="Productos Congelados",
            barcode=barcode,
        )
        db.add(sku)
        created += 1
        print(f"  Created: {full_name}")

    db.commit()
    db.close()

    print(f"\nDone! Created: {created}, Skipped: {skipped}")


if __name__ == "__main__":
    print("Seeding Productos Congelados...")
    seed_congelados()
