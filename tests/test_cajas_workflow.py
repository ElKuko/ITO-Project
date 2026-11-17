"""End-to-end API test of the cajas (box count) visit workflow.

Run from the project root:  python -m pytest tests/
Uses its own throwaway SQLite database.
"""

import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"

from fastapi.testclient import TestClient  # noqa: E402

from backend.database import SessionLocal  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models import SKU, Store, StoreSKUApproval  # noqa: E402
from backend.routers.visits import _current_quarter  # noqa: E402

client = TestClient(app)


def login(username, password):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c4944415408d763f8ffff3f0005fe02fea7d6a4b30000000049454e44ae426082"
)


def upload_sku_photo(visit, headers, segment, sku_ids, photo_type="sku_photo_after"):
    r = client.post(
        f"/api/visits/{visit}/photos", headers=headers,
        files={"file": ("p.png", PNG, "image/png")},
        data={"photo_type": photo_type, "segment": segment, "sku_ids": ",".join(map(str, sku_ids)), "run_cv": "false"},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def approve_skus(store_id):
    """Approve 2 Produce and 2 Provisiones SKUs; Congelados gets none."""
    db = SessionLocal()
    db.query(StoreSKUApproval).filter_by(store_id=store_id).delete()
    by_section = {}
    for section in ("produce", "provisiones"):
        for sku in db.query(SKU).filter_by(section=section, is_active=True).limit(2):
            db.add(StoreSKUApproval(store_id=store_id, sku_id=sku.id, quarter=_current_quarter()))
            by_section.setdefault(section, []).append(sku.id)
    db.commit()
    db.close()
    return by_section


def test_cajas_workflow():
    merch, admin = login("merch1", "merch123"), login("admin", "admin123")
    db = SessionLocal()
    store_id = db.query(Store).first().id
    db.close()
    skus = approve_skus(store_id)
    p1, p2 = skus["produce"]

    visit = client.post("/api/visits/start", json={"store_id": store_id}, headers=merch).json()["visit_id"]

    def status():
        r = client.get(f"/api/visits/{visit}/sku-report/summary", headers=merch).json()
        return {s["segment"]: s["status"] for s in r}

    def save(segment, items, headers=merch):
        return client.put(f"/api/visits/{visit}/sku-report", json={"segment": segment, "items": items}, headers=headers)

    # Sections start pending; a section with no approved SKUs doesn't apply
    assert status() == {"produce": "pendiente", "provisiones": "pendiente", "congelados": "no_aplica"}
    report = client.get(f"/api/visits/{visit}/sku-report?segment=produce", headers=merch).json()
    assert [s["cajas_puestas"] for s in report["skus"]] == [None, None]  # blank, not 0

    # Validation: non-negative, both counts together, only approved SKUs of the section
    assert save("produce", [{"sku_id": p1, "cajas_puestas": -1, "cajas_faltaron": 0}]).status_code == 422
    assert save("produce", [{"sku_id": p1, "cajas_puestas": 1}]).status_code == 400
    assert save("produce", [{"sku_id": skus["provisiones"][0], "cajas_puestas": 1, "cajas_faltaron": 0}]).status_code == 400

    assert save("produce", [{"sku_id": p1, "cajas_puestas": 4, "cajas_faltaron": 3}]).json()["status"] == "en_progreso"
    r = client.put(f"/api/visits/{visit}/complete", json={}, headers=merch)
    assert r.status_code == 400  # sections incomplete

    # 0/0 is a valid, explicit entry
    save("produce", [{"sku_id": p1, "cajas_puestas": 4, "cajas_faltaron": 2},
                     {"sku_id": p2, "cajas_puestas": 0, "cajas_faltaron": 0}])
    save("provisiones", [{"sku_id": i, "cajas_puestas": 1, "cajas_faltaron": 1} for i in skus["provisiones"]])

    # Counts alone don't complete a section: every SKU needs a "foto antes" and a "foto después"
    assert status() == {"produce": "en_progreso", "provisiones": "en_progreso", "congelados": "no_aplica"}
    upload_sku_photo(visit, merch, "produce", [p1, p2])  # después only
    assert status()["produce"] == "en_progreso"
    upload_sku_photo(visit, merch, "produce", [p1], photo_type="sku_photo")
    assert status()["produce"] == "en_progreso"  # p2 still lacks antes
    r = client.put(f"/api/visits/{visit}/complete", json={}, headers=merch)
    assert r.status_code == 400 and "sin completar" in r.json()["detail"]
    upload_sku_photo(visit, merch, "produce", [p2], photo_type="sku_photo")
    for kind in ("sku_photo", "sku_photo_after"):  # one photo can cover several SKUs
        upload_sku_photo(visit, merch, "provisiones", skus["provisiones"], photo_type=kind)
    assert status() == {"produce": "completado", "provisiones": "completado", "congelados": "no_aplica"}
    kinds = sorted(p["kind"] for p in client.get(f"/api/visits/{visit}/sku-report?segment=produce", headers=merch).json()["photos"])
    assert kinds == ["antes", "antes", "despues"]

    # Submission is idempotent
    first = client.put(f"/api/visits/{visit}/complete", json={"notes": "ok"}, headers=merch)
    again = client.put(f"/api/visits/{visit}/complete", json={"notes": "dup"}, headers=merch)
    assert first.status_code == again.status_code == 200
    assert again.json()["notes"] == "ok" and again.json()["end_time"] == first.json()["end_time"]

    # Only admins edit after submission; a partial save doesn't drop other SKUs
    assert save("produce", [{"sku_id": p1, "cajas_puestas": 9, "cajas_faltaron": 2}]).status_code == 400
    p1_photos = [p["id"] for p in client.get(f"/api/visits/{visit}/sku-report?segment=produce", headers=admin).json()["photos"]
                 if p1 in p["sku_ids"]]
    assert save("produce", [{"sku_id": p1, "cajas_puestas": 5, "cajas_faltaron": 2, "photo_ids": p1_photos}], admin).status_code == 200
    assert status()["produce"] == "completado"

    # Catalog changes don't alter submitted history
    db = SessionLocal()
    original = db.query(SKU).get(p1).name
    db.query(SKU).filter_by(id=p1).update({"name": "RENAMED"})
    db.commit()
    db.close()
    names = [s["name"] for s in client.get(f"/api/visits/{visit}/sku-report?segment=produce", headers=admin).json()["skus"]]
    assert original in names and "RENAMED" not in names

    # Every change is in the history, including the admin correction
    history = client.get(f"/api/visits/{visit}/sku-report/history", headers=admin).json()
    p1_puestas = [(e["old_value"], e["new_value"], e["after_submission"])
                  for e in history if e["sku_id"] == p1 and e["field"] == "cajas_puestas"]
    assert p1_puestas == [(None, 4, False), (4, 5, True)]

    # Reporting
    rep = client.get("/api/reports/cajas?group_by=section", headers=admin).json()
    assert rep["totals"]["cajas_puestas"] == 7 and rep["totals"]["cajas_faltaron"] == 4
    assert rep["totals"]["placement_completion_rate"] == round(7 / 11, 4)
    csv = client.get("/api/reports/cajas/records?format=csv", headers=admin).text
    assert csv.startswith("visit_sku_id,visit_id,store_id") and len(csv.strip().splitlines()) == 5
    assert client.get("/api/reports/cajas", headers=merch).status_code == 403


def test_approvals_carry_forward_from_earlier_quarter():
    """Approvals saved in a past quarter still apply until a newer list is saved."""
    from backend.quarters import current_quarter

    merch = login("merch1", "merch123")
    db = SessionLocal()
    store_id = db.query(Store).order_by(Store.id.desc()).first().id
    db.query(StoreSKUApproval).filter_by(store_id=store_id).delete()
    produce = [s.id for s in db.query(SKU).filter_by(section="produce", is_active=True).limit(3)]
    for sku_id in produce:
        db.add(StoreSKUApproval(store_id=store_id, sku_id=sku_id, quarter="2020-Q1"))
    db.add(StoreSKUApproval(store_id=store_id, sku_id=produce[0], quarter="2099-Q1"))  # future: ignored
    db.commit()
    db.close()

    tab = client.get(f"/api/approvals/?store_id={store_id}&effective=true", headers=merch).json()
    assert sorted(a["sku_id"] for a in tab) == sorted(produce)

    visit = client.post("/api/visits/start", json={"store_id": store_id}, headers=merch).json()["visit_id"]
    report = client.get(f"/api/visits/{visit}/sku-report?segment=produce", headers=merch).json()
    assert sorted(s["id"] for s in report["skus"]) == sorted(produce)

    # Saving a new list for the current quarter replaces the carried-forward one
    r = client.put("/api/approvals/bulk", headers=merch,
                   json={"store_id": store_id, "quarter": current_quarter(), "sku_ids": produce[:1]})
    assert r.status_code == 200
    report = client.get(f"/api/visits/{visit}/sku-report?segment=produce", headers=merch).json()
    assert [s["id"] for s in report["skus"]] == produce[:1]
