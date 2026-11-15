"""Demo store behavior the agent demo depends on. Run: backend/.venv/bin/pytest demo-store/tests"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402

client = TestClient(server.app)


def test_pages_are_empty_shells_rendered_by_javascript():
    for path in ("/", "/product/trail-runner", "/delivery"):
        html = client.get(path).text
        assert '<div id="app"></div>' in html and "Trail Runner" not in html


def test_size_nine_under_3000_has_exactly_one_running_shoe_in_stock():
    products = client.get("/api/products").json()["products"]
    matches = [
        p["slug"]
        for p in products
        if p["category"] == "Running" and p["price"] < 3000 and p["sizes"].get("9", 0) > 0
    ]
    assert matches == ["trail-runner"]


def test_delivery_requires_login_then_works():
    fresh = TestClient(server.app)
    assert fresh.get("/api/delivery", params={"pin": "560001"}).status_code == 401
    assert fresh.post("/api/login", json={"email": "demo@northstar.example", "password": "x"}).status_code == 401
    assert fresh.post("/api/login", json=server.DEMO_ACCOUNT).status_code == 200
    assert fresh.get("/api/delivery", params={"pin": "560001"}).json()["estimate"] == "2–3 working days"


def test_cart_rejects_out_of_stock_and_places_orders():
    shopper = TestClient(server.app)
    assert shopper.post("/api/cart", json={"slug": "city-walker", "size": "9"}).status_code == 409
    assert shopper.post("/api/cart", json={"slug": "trail-runner", "size": "9"}).status_code == 200
    order = shopper.post("/api/orders").json()
    assert order["items"][0]["slug"] == "trail-runner" and order["total"] == 2799
    assert shopper.get("/api/cart").json()["items"] == []
