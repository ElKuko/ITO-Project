"""Add General route and link existing stores to it.

Run this to fix existing databases where stores aren't linked to routes.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, engine, Base
from backend.models import User, Store, Route, RouteStop

# Ensure all tables exist (creates routes/route_stops if missing)
Base.metadata.create_all(bind=engine)


def add_general_route():
    db = SessionLocal()

    # Check if General route already exists
    route = db.query(Route).filter(Route.name == "General").first()
    if route:
        print("General route already exists. Skipping creation.")
    else:
        # Find a merchandiser to assign
        merch = db.query(User).filter(User.role == "merchandiser").first()
        if not merch:
            print("No merchandiser found. Please create a merchandiser first.")
            db.close()
            return

        route = Route(
            name="General",
            merchandiser_id=merch.id,
            is_active=True,
        )
        db.add(route)
        db.flush()
        print(f"Created General route, assigned to: {merch.full_name}")

    # Get all stores not already linked to any route
    all_stores = db.query(Store).all()

    stops_created = 0
    for idx, store in enumerate(all_stores):
        # Check if store already has a route stop
        existing = db.query(RouteStop).filter(RouteStop.store_id == store.id).first()
        if not existing:
            stop = RouteStop(
                route_id=route.id,
                store_id=store.id,
                day="Lunes",
                visit_order=idx + 1,
            )
            db.add(stop)
            stops_created += 1
            print(f"  Linked store: {store.name}")

    db.commit()
    db.close()

    print(f"\nDone! Linked {stops_created} stores to General route.")
    print("Visits to these stores will now appear in 'Por Ruta' tab.")


if __name__ == "__main__":
    add_general_route()
