"""Seed the database with sample data for development/demo."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import engine, SessionLocal, Base
from backend.models import User, Store, SKU, StoreSKUApproval, StoreVisit, VisitSKUAction
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

    # ── Stores (supermarkets in Puerto Rico) ──────────────────────────
    stores = [
        Store(name="Pueblo Supermarket — Condado", region="Metro", address="Av. Ashford 1234, San Juan, PR 00907", latitude=18.4571, longitude=-66.0726),
        Store(name="Econo — Bayamón", region="Metro", address="Carr. 2 Km 11.2, Bayamón, PR 00961", latitude=18.3985, longitude=-66.1553),
        Store(name="Selectos — Carolina", region="Metro", address="Av. 65 de Infantería, Carolina, PR 00987", latitude=18.3804, longitude=-65.9573),
        Store(name="Ralph's Food Warehouse — Mayagüez", region="Oeste", address="Carr. 2 Km 158, Mayagüez, PR 00682", latitude=18.2013, longitude=-67.1397),
        Store(name="Pueblo Supermarket — Ponce", region="Sur", address="Av. Las Américas, Ponce, PR 00717", latitude=18.0111, longitude=-66.6141),
        Store(name="Econo — Caguas", region="Este", address="Carr. 1 Km 33.5, Caguas, PR 00725", latitude=18.2341, longitude=-66.0485),
    ]
    db.add_all(stores)
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

    # ── Store-SKU Approvals (Q1 2026) ────────────────────────────────
    quarter = "2026-Q1"
    approvals = []
    for store in stores:
        # Each store gets 5-8 approved SKUs
        approved_skus = skus[:8] if store.region == "Metro" else skus[:5]
        for sku in approved_skus:
            approvals.append(StoreSKUApproval(
                store_id=store.id, sku_id=sku.id, quarter=quarter
            ))
    db.add_all(approvals)
    db.flush()

    # ── Sample Store Visits ──────────────────────────────────────────
    from datetime import datetime, timedelta

    visit1 = StoreVisit(
        store_id=stores[0].id, user_id=merch1.id,
        visited_at=datetime.utcnow() - timedelta(days=2),
        latitude=18.4571, longitude=-66.0726,
        notes="Shelf space looks good overall. Coconut water needs restock.",
    )
    db.add(visit1)
    db.flush()

    db.add_all([
        VisitSKUAction(visit_id=visit1.id, sku_id=skus[0].id, action_type="needs_refill", notes="Only 2 facings left"),
        VisitSKUAction(visit_id=visit1.id, sku_id=skus[2].id, action_type="placed_on_shelf", notes="Restocked from backroom"),
        VisitSKUAction(visit_id=visit1.id, sku_id=skus[4].id, action_type="needs_order", notes="Warehouse empty"),
    ])

    visit2 = StoreVisit(
        store_id=stores[1].id, user_id=merch1.id,
        visited_at=datetime.utcnow() - timedelta(days=10),
        notes="Several products missing from shelf.",
    )
    db.add(visit2)
    db.flush()

    db.add_all([
        VisitSKUAction(visit_id=visit2.id, sku_id=skus[0].id, action_type="needs_order", notes="Not in warehouse"),
        VisitSKUAction(visit_id=visit2.id, sku_id=skus[1].id, action_type="needs_refill"),
        VisitSKUAction(visit_id=visit2.id, sku_id=skus[3].id, action_type="needs_order"),
    ])

    visit3 = StoreVisit(
        store_id=stores[3].id, user_id=merch2.id,
        visited_at=datetime.utcnow() - timedelta(days=1),
        latitude=18.2013, longitude=-67.1397,
    )
    db.add(visit3)
    db.flush()

    db.add_all([
        VisitSKUAction(visit_id=visit3.id, sku_id=skus[0].id, action_type="placed_on_shelf"),
        VisitSKUAction(visit_id=visit3.id, sku_id=skus[1].id, action_type="placed_on_shelf"),
    ])

    db.commit()
    db.close()

    print("Database seeded successfully!")
    print("  Users: admin/admin123 (president), merch1/merch123, merch2/merch123")
    print(f"  Stores: {len(stores)}")
    print(f"  SKUs: {len(skus)}")
    print(f"  Approvals: {len(approvals)}")
    print(f"  Sample visits: 3")


if __name__ == "__main__":
    seed()
