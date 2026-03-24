"""Seed the database with sample data for development/demo.

Updated for 6-step visit workflow with:
- start_time/end_time instead of visited_at
- condition checks (prices_on_gondola, pop_material_present, product_presentable)
- new action types: gondola_llena, se_relleno, orden
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import engine, SessionLocal, Base
from backend.models import User, SKU, Route
from backend.auth import hash_password


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Check if data already exists
    if db.query(User).first():
        print("Database already seeded. Skipping.")
        db.close()
        return

    # ── Users ─────────────────────────────────────────────────────────
    admin = User(
        username="admin",
        password_hash=hash_password("admin123"),
        full_name="Carlos Rivera (President)",
        role="admin",
        region="Metro",
    )
    merch1 = User(
        username="merch1",
        password_hash=hash_password("merch123"),
        full_name="Maria Santos",
        role="merchandiser",
        region="Metro",
    )
    merch2 = User(
        username="merch2",
        password_hash=hash_password("merch123"),
        full_name="Jose Rodriguez",
        role="merchandiser",
        region="Oeste",
    )
    db.add_all([admin, merch1, merch2])
    db.flush()

    # ── Routes ─────────────────────────────────────────────────────────
    # Create the Norte route (stores will be added by seed_ruta_norte.py)
    norte_route = Route(
        name="Norte",
        merchandiser_id=merch1.id,
        is_active=True,
    )
    db.add(norte_route)
    db.flush()

    # ── SKUs (Ito brand products) ─────────────────────────────────────
    skus = [
        SKU(name="Ito Coconut Water 500ml", brand="Ito", category="Beverages", barcode="7501234000101"),
        SKU(name="Ito Coconut Water 1L", brand="Ito", category="Beverages", barcode="7501234000102"),
        SKU(name="Ito Mango Nectar 500ml", brand="Ito", category="Beverages", barcode="7501234000201"),
        SKU(name="Ito Passion Fruit Juice 500ml", brand="Ito", category="Beverages", barcode="7501234000301"),
        SKU(name="Ito Guava Juice 500ml", brand="Ito", category="Beverages", barcode="7501234000401"),
        SKU(name="Ito Pineapple Juice 1L", brand="Ito", category="Beverages", barcode="7501234000501"),
        SKU(name="Ito Sparkling Coconut Water 330ml", brand="Ito", category="Beverages", barcode="7501234000601"),
        SKU(name="Ito Coconut Milk 400ml", brand="Ito", category="Dairy Alternative", barcode="7501234000701"),
        SKU(name="Ito Aloe Vera Drink 500ml", brand="Ito", category="Beverages", barcode="7501234000801"),
        SKU(name="Ito Mixed Tropical Juice 1L", brand="Ito", category="Beverages", barcode="7501234000901"),
    ]
    db.add_all(skus)
    db.flush()

    # Note: Store-SKU approvals and sample visits are not created here.
    # Run seed_ruta_norte.py to add stores, then manually create approvals as needed.

    db.commit()
    db.close()

    print("Database seeded successfully!")
    print("  Users: admin/admin123 (president), merch1/merch123, merch2/merch123")
    print("  Routes: 1 (Norte)")
    print(f"  SKUs: {len(skus)}")
    print("")
    print("Next: Run 'python scripts/seed_ruta_norte.py' to add stores.")


if __name__ == "__main__":
    seed()
