"""Master seed script for all Ito SKUs"""

from scripts.seed_skus_refrigerados import seed_refrigerados
from scripts.seed_skus_congelados import seed_congelados
from scripts.seed_skus_secos import seed_secos


def seed_all():
    print("=" * 50)
    print("SEEDING ALL ITO SKUS")
    print("=" * 50)

    print("\n[1/3] Productos Refrigerados...")
    seed_refrigerados()

    print("\n[2/3] Productos Congelados...")
    seed_congelados()

    print("\n[3/3] Productos Secos...")
    seed_secos()

    print("\n" + "=" * 50)
    print("ALL DONE!")
    print("=" * 50)


if __name__ == "__main__":
    seed_all()
