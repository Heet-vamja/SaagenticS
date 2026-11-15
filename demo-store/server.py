"""Northstar Shoes: a fictional demo store with typical problems for AI agents.

Deliberate problems (do not "fix" them here; AgentLane's variant is the fix):
- product pages render only with JavaScript (the HTML is an empty shell);
- an offer pop-up covers the page, closed by an unlabeled element;
- the size picker is a custom widget with no labels or roles;
- the delivery estimate requires login.

State (sessions, carts, orders) lives in memory so every run starts clean.
Run with: uvicorn server:app --port 4000
"""

import json
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent
CATALOG = json.loads((ROOT / "catalog.json").read_text())
PRODUCTS = {item["slug"]: item for item in CATALOG["products"]}
DEMO_ACCOUNT = {"email": "demo@northstar.example", "password": "northstar"}
SESSION_COOKIE = "ns_session"
CART_COOKIE = "ns_cart"

app = FastAPI(title="Northstar Shoes (demo)", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

sessions: set[str] = set()
carts: dict[str, list[dict]] = {}
orders: list[dict] = []


class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=100)


class CartItem(BaseModel):
    slug: str = Field(max_length=80)
    size: str = Field(max_length=4)


def shell() -> FileResponse:
    # Every page is the same empty shell; static/app.js renders the content.
    return FileResponse(ROOT / "static" / "index.html", media_type="text/html")


@app.get("/", include_in_schema=False)
@app.get("/product/{slug}", include_in_schema=False)
@app.get("/cart", include_in_schema=False)
@app.get("/login", include_in_schema=False)
@app.get("/delivery", include_in_schema=False)
@app.get("/policies", include_in_schema=False)
def page(slug: str | None = None):
    return shell()


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return "User-agent: *\nAllow: /\n"


@app.get("/api/products")
def products():
    return {"store": CATALOG["store"], "currency": CATALOG["currency"], "products": CATALOG["products"]}


@app.get("/api/products/{slug}")
def product(slug: str):
    if slug not in PRODUCTS:
        raise HTTPException(404, "Product not found")
    return PRODUCTS[slug]


@app.get("/api/policies")
def policies():
    return CATALOG["policies"]


@app.post("/api/login")
def login(body: Login, response: Response):
    if body.email.strip().lower() != DEMO_ACCOUNT["email"] or body.password != DEMO_ACCOUNT["password"]:
        raise HTTPException(401, "Email or password is incorrect")
    token = secrets.token_urlsafe(24)
    sessions.add(token)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return {"signed_in": True}


@app.get("/api/delivery")
def delivery(pin: str, request: Request):
    if request.cookies.get(SESSION_COOKIE) not in sessions:
        raise HTTPException(401, "Sign in to check delivery")
    if not (pin.isdigit() and len(pin) == 6):
        raise HTTPException(422, "Enter a 6-digit PIN code")
    days = "2–3" if pin.startswith(("11", "40", "56")) else "3–5"
    return {"pin": pin, "estimate": f"{days} working days", "free_over": 1500}


def cart_id(request: Request, response: Response) -> str:
    current = request.cookies.get(CART_COOKIE)
    if current in carts:
        return current
    current = secrets.token_urlsafe(16)
    carts[current] = []
    response.set_cookie(CART_COOKIE, current, httponly=True, samesite="lax")
    return current


@app.get("/api/cart")
def cart(request: Request, response: Response):
    items = carts[cart_id(request, response)]
    return {"items": items, "total": sum(item["price"] for item in items)}


@app.post("/api/cart")
def add_to_cart(body: CartItem, request: Request, response: Response):
    item = PRODUCTS.get(body.slug)
    if not item or body.size not in item["sizes"]:
        raise HTTPException(404, "Product or size not found")
    if item["sizes"][body.size] < 1:
        raise HTTPException(409, "That size is out of stock")
    items = carts[cart_id(request, response)]
    items.append({"slug": item["slug"], "name": item["name"], "size": body.size, "price": item["price"]})
    return {"items": items, "total": sum(entry["price"] for entry in items)}


@app.post("/api/orders")
def place_order(request: Request, response: Response):
    items = carts[cart_id(request, response)]
    if not items:
        raise HTTPException(409, "Your cart is empty")
    order = {"id": f"NS-{len(orders) + 1001}", "items": list(items), "total": sum(i["price"] for i in items)}
    orders.append(order)
    items.clear()
    return order
