"""Seed script for Ruta Norte stores and route stops"""

from backend.database import SessionLocal
from backend.models import User, Store, Route, RouteStop
from backend.auth import hash_password

# Chain extraction patterns
CHAIN_PATTERNS = [
    "Econo", "Selectos", "SuperMax", "Walmart", "Sam's", "Pueblo",
    "Famcoop", "Agranel", "Mr. Special", "JF Montalvo",
    "Union", "Hatillo Cash & Carry"
]

# Ruta Norte data - Michael Rivera
RUTA_NORTE = [
    # Lunes
    {"day": "Lunes", "order": 1, "pueblo": "Vega Baja", "tienda": "Econo Playa"},
    {"day": "Lunes", "order": 2, "pueblo": "Vega Baja", "tienda": "Econo Plaza"},
    {"day": "Lunes", "order": 3, "pueblo": "Vega Baja", "tienda": "Union Vega Baja Cash & Carry"},
    {"day": "Lunes", "order": 4, "pueblo": "Vega Baja", "tienda": "SuperMax"},
    {"day": "Lunes", "order": 5, "pueblo": "Vega Alta", "tienda": "Selectos Sabana"},
    {"day": "Lunes", "order": 6, "pueblo": "Vega Alta", "tienda": "Selectos Pámpanos"},
    {"day": "Lunes", "order": 7, "pueblo": "Vega Alta", "tienda": "Mr. Special"},
    {"day": "Lunes", "order": 8, "pueblo": "Vega Alta", "tienda": "Carmelita Famcoop"},
    {"day": "Lunes", "order": 9, "pueblo": "Dorado", "tienda": "Famcoop"},
    {"day": "Lunes", "order": 10, "pueblo": "Dorado", "tienda": "JF Montalvo"},
    {"day": "Lunes", "order": 11, "pueblo": "Dorado", "tienda": "SuperMax"},
    {"day": "Lunes", "order": 12, "pueblo": "Dorado", "tienda": "SuperMax Paseo Dorado"},
    {"day": "Lunes", "order": 13, "pueblo": "Manatí", "tienda": "Econo"},
    {"day": "Lunes", "order": 14, "pueblo": "Manatí", "tienda": "SuperMax"},
    {"day": "Lunes", "order": 15, "pueblo": "Manatí", "tienda": "Walmart"},
    # Martes
    {"day": "Martes", "order": 1, "pueblo": "Arecibo", "tienda": "Econo"},
    {"day": "Martes", "order": 2, "pueblo": "Arecibo", "tienda": "Famcoop 4 Calles"},
    {"day": "Martes", "order": 3, "pueblo": "Arecibo", "tienda": "Famcoop Bayajá"},
    {"day": "Martes", "order": 4, "pueblo": "Arecibo", "tienda": "Famcoop Sabana Hoyos"},
    {"day": "Martes", "order": 5, "pueblo": "Arecibo", "tienda": "Hatillo Cash & Carry"},
    {"day": "Martes", "order": 6, "pueblo": "Arecibo", "tienda": "Pueblo"},
    {"day": "Martes", "order": 7, "pueblo": "Arecibo", "tienda": "Selectos"},
    {"day": "Martes", "order": 8, "pueblo": "Barceloneta", "tienda": "Econo"},
    {"day": "Martes", "order": 9, "pueblo": "Barceloneta", "tienda": "JF Montalvo"},
    {"day": "Martes", "order": 10, "pueblo": "Barceloneta", "tienda": "Walmart"},
    {"day": "Martes", "order": 11, "pueblo": "Utuado", "tienda": "Econo"},
    {"day": "Martes", "order": 12, "pueblo": "Utuado", "tienda": "Famcoop Caguana"},
    {"day": "Martes", "order": 13, "pueblo": "Utuado", "tienda": "Selectos"},
    {"day": "Martes", "order": 14, "pueblo": "Utuado", "tienda": "Agranel"},
    {"day": "Martes", "order": 15, "pueblo": "Florida", "tienda": "Econo"},
    {"day": "Martes", "order": 16, "pueblo": "Florida", "tienda": "Famcoop Selgas"},
    # Miércoles
    {"day": "Miércoles", "order": 1, "pueblo": "Hatillo", "tienda": "Union Hatillo Cash & Carry"},
    {"day": "Miércoles", "order": 2, "pueblo": "Hatillo", "tienda": "Sam's"},
    {"day": "Miércoles", "order": 3, "pueblo": "Hatillo", "tienda": "Selectos"},
    {"day": "Miércoles", "order": 4, "pueblo": "Hatillo", "tienda": "Walmart"},
    {"day": "Miércoles", "order": 5, "pueblo": "Quebradillas", "tienda": "Hatillo Cash & Carry"},
    {"day": "Miércoles", "order": 6, "pueblo": "Isabela", "tienda": "Econo"},
    {"day": "Miércoles", "order": 7, "pueblo": "Isabela", "tienda": "Union Cash & Carry"},
    {"day": "Miércoles", "order": 8, "pueblo": "Isabela", "tienda": "Selectos"},
    {"day": "Miércoles", "order": 9, "pueblo": "Isabela", "tienda": "Mr. Special"},
    {"day": "Miércoles", "order": 10, "pueblo": "Isabela", "tienda": "Walmart"},
    {"day": "Miércoles", "order": 11, "pueblo": "Camuy", "tienda": "Econo"},
    {"day": "Miércoles", "order": 12, "pueblo": "Camuy", "tienda": "Famcoop Quebrada Xtra"},
    {"day": "Miércoles", "order": 13, "pueblo": "Camuy", "tienda": "Famcoop Mr. trigo"},
    {"day": "Miércoles", "order": 14, "pueblo": "Camuy", "tienda": "Hatillo Cash & Carry"},
    {"day": "Miércoles", "order": 15, "pueblo": "Camuy", "tienda": "JF Montalvo"},
    {"day": "Miércoles", "order": 16, "pueblo": "Camuy", "tienda": "Agranel"},
    # Jueves
    {"day": "Jueves", "order": 1, "pueblo": "Jayuya", "tienda": "Econo"},
    {"day": "Jueves", "order": 2, "pueblo": "Jayuya", "tienda": "Agranel"},
    {"day": "Jueves", "order": 3, "pueblo": "Adjuntas", "tienda": "Selectos"},
    {"day": "Jueves", "order": 4, "pueblo": "Lares", "tienda": "Econo"},
    {"day": "Jueves", "order": 5, "pueblo": "Lares", "tienda": "Famcoop Mijan"},
    {"day": "Jueves", "order": 6, "pueblo": "Lares", "tienda": "Union Lares Cash & Carry"},
    {"day": "Jueves", "order": 7, "pueblo": "Lares", "tienda": "Mr. Special"},
    {"day": "Jueves", "order": 8, "pueblo": "San Sebastián", "tienda": "Econo"},
    {"day": "Jueves", "order": 9, "pueblo": "San Sebastián", "tienda": "Selectos"},
    {"day": "Jueves", "order": 10, "pueblo": "San Sebastián", "tienda": "Mr. Special"},
    {"day": "Jueves", "order": 11, "pueblo": "Moca", "tienda": "Selectos"},
    {"day": "Jueves", "order": 12, "pueblo": "Moca", "tienda": "Mr. Special"},
    # Viernes
    {"day": "Viernes", "order": 1, "pueblo": "Añasco", "tienda": "Union L/A Añasco Cash & Carry"},
    {"day": "Viernes", "order": 2, "pueblo": "Añasco", "tienda": "Selectos"},
    {"day": "Viernes", "order": 3, "pueblo": "Añasco", "tienda": "Mr. Special"},
    {"day": "Viernes", "order": 4, "pueblo": "Aguadilla", "tienda": "Econo Gate 5"},
    {"day": "Viernes", "order": 5, "pueblo": "Aguadilla", "tienda": "Pueblo Aguadilla Shopping Mall"},
    {"day": "Viernes", "order": 6, "pueblo": "Aguadilla", "tienda": "Selectos Montana Industrial Park"},
    {"day": "Viernes", "order": 7, "pueblo": "Aguadilla", "tienda": "Selectos Plaza Borinquén"},
    {"day": "Viernes", "order": 8, "pueblo": "Aguadilla", "tienda": "Famcoop"},
    {"day": "Viernes", "order": 9, "pueblo": "Aguadilla", "tienda": "Agranel"},
    {"day": "Viernes", "order": 10, "pueblo": "Aguada", "tienda": "Econo"},
    {"day": "Viernes", "order": 11, "pueblo": "Aguada", "tienda": "Selectos"},
    {"day": "Viernes", "order": 12, "pueblo": "Aguada", "tienda": "Mr. Special"},
    {"day": "Viernes", "order": 13, "pueblo": "Aguada", "tienda": "Agranel"},
    {"day": "Viernes", "order": 14, "pueblo": "Rincón", "tienda": "Econo"},
    {"day": "Viernes", "order": 15, "pueblo": "Rincón", "tienda": "Famcoop Edward's"},
]


def extract_chain(tienda_name):
    """Extract chain name from store name."""
    name_lower = tienda_name.lower()

    if "econo" in name_lower:
        return "Econo"
    if "selectos" in name_lower:
        return "Selectos"
    if "supermax" in name_lower:
        return "SuperMax"
    if "walmart" in name_lower:
        return "Walmart"
    if "sam's" in name_lower:
        return "Sam's"
    if "pueblo" in name_lower:
        return "Pueblo"
    if "famcoop" in name_lower or "carmelita" in name_lower:
        return "Famcoop"
    if "agranel" in name_lower:
        return "Agranel"
    if "mr. special" in name_lower:
        return "Mr. Special"
    if "jf montalvo" in name_lower:
        return "JF Montalvo"
    if "union" in name_lower or "cash & carry" in name_lower:
        return "Cash & Carry"

    return None


def seed_ruta_norte():
    db = SessionLocal()

    # 1. Create or get merchandiser
    merchandiser = db.query(User).filter(User.full_name == "Michael Rivera").first()
    if not merchandiser:
        merchandiser = User(
            username="mrivera",
            password_hash=hash_password("temp123"),
            full_name="Michael Rivera",
            role="merchandiser",
            region="Norte",
        )
        db.add(merchandiser)
        db.flush()
        print(f"  Created merchandiser: Michael Rivera")
    else:
        print(f"  Found existing merchandiser: Michael Rivera")

    # 2. Create or get route
    route = db.query(Route).filter(Route.name == "Norte").first()
    if not route:
        route = Route(name="Norte", merchandiser_id=merchandiser.id)
        db.add(route)
        db.flush()
        print(f"  Created route: Norte")
    else:
        print(f"  Found existing route: Norte")

    # 3. Create stores and route stops
    stores_created = 0
    stops_created = 0

    for stop_data in RUTA_NORTE:
        pueblo = stop_data["pueblo"]
        tienda = stop_data["tienda"]
        chain = extract_chain(tienda)

        # Create unique store name with pueblo
        store_name = f"{tienda} - {pueblo}"

        # Check if store exists
        store = db.query(Store).filter(Store.name == store_name).first()
        if not store:
            store = Store(
                name=store_name,
                chain=chain,
                pueblo=pueblo,
                region="Norte",
            )
            db.add(store)
            db.flush()
            stores_created += 1

        # Check if route stop exists
        existing_stop = db.query(RouteStop).filter(
            RouteStop.route_id == route.id,
            RouteStop.store_id == store.id,
            RouteStop.day == stop_data["day"]
        ).first()

        if not existing_stop:
            route_stop = RouteStop(
                route_id=route.id,
                store_id=store.id,
                day=stop_data["day"],
                visit_order=stop_data["order"],
            )
            db.add(route_stop)
            stops_created += 1

    db.commit()
    db.close()

    print(f"\nDone! Stores created: {stores_created}, Route stops created: {stops_created}")


if __name__ == "__main__":
    print("Seeding Ruta Norte...")
    seed_ruta_norte()
