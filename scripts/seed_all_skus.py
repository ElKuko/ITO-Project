"""Master seed script for all Ito data (SKUs and Routes)"""

from scripts.seed_skus_refrigerados import seed_refrigerados
from scripts.seed_skus_congelados import seed_congelados
from scripts.seed_skus_secos import seed_secos
from scripts.seed_ruta_norte import seed_ruta_norte


def seed_all():
    print("=" * 50)
    print("SEEDING ALL ITO DATA")
    print("=" * 50)

    print("\n[1/4] Productos Refrigerados...")
    seed_refrigerados()

    print("\n[2/4] Productos Congelados...")
    seed_congelados()

    print("\n[3/4] Productos Secos...")
    seed_secos()

    print("\n[4/4] Ruta Norte (stores & route)...")
    seed_ruta_norte()

    print("\n" + "=" * 50)
    print("ALL DONE!")
    print("=" * 50)


if __name__ == "__main__":
    seed_all()
