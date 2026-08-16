from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from motor.motor_asyncio import AsyncIOMotorClient

# ---------- Config ----------
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']
JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALG = "HS256"

use_mock = os.environ.get("USE_MOCK_DB", "").lower() in ("1", "true", "yes")
if not use_mock:
    try:
        from pymongo import MongoClient
        test_client = MongoClient(
            MONGO_URL,
            serverSelectionTimeoutMS=1000,
            connectTimeoutMS=1000,
        )
        test_client.admin.command('ping')
        test_client.close()
        client = AsyncIOMotorClient(
            MONGO_URL,
            serverSelectionTimeoutMS=int(os.environ.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", "1500")),
            connectTimeoutMS=int(os.environ.get("MONGO_CONNECT_TIMEOUT_MS", "1500")),
        )
    except Exception:
        use_mock = True

if use_mock:
    import mongomock_motor
    client = mongomock_motor.AsyncMongoMockClient()

db = client[DB_NAME]

app = FastAPI(title="RdCloth ERP API")
api = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rdcloth")

# ---------- Helpers ----------
def new_id() -> str:
    return str(uuid.uuid4())

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def hash_password(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()

DEFAULT_OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "rddev@gmail.com").lower()
DEFAULT_OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "rdcloth2026")

FALLBACK_USERS = {
    DEFAULT_OWNER_EMAIL: {
        "id": "owner-demo", "email": DEFAULT_OWNER_EMAIL, "name": "RdCloth Owner", "role": "owner",
        "password_hash": hash_password(DEFAULT_OWNER_PASSWORD),
    },
    "admin@rdcloth.id": {
        "id": "admin-demo", "email": "admin@rdcloth.id", "name": "Admin Staff", "role": "admin",
        "password_hash": hash_password("admin123"),
    },
    "production@rdcloth.id": {
        "id": "production-demo", "email": "production@rdcloth.id", "name": "Production Staff", "role": "production",
        "password_hash": hash_password("production123"),
    },
    "finance@rdcloth.id": {
        "id": "finance-demo", "email": "finance@rdcloth.id", "name": "Finance Staff", "role": "finance",
        "password_hash": hash_password("finance123"),
    },
}

def verify_password(pwd: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pwd.encode(), hashed.encode())
    except Exception:
        return False

def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id, "email": email, "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

    try:
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    except Exception:
        user = None

    if not user:
        fallback = next((u for u in FALLBACK_USERS.values() if u["id"] == payload["sub"]), None)
        if not fallback:
            raise HTTPException(401, "User not found")
        user = {k: v for k, v in fallback.items() if k != "password_hash"}
    return user

# Role-based permissions
ROLE_MODULES = {
    "owner": {"*"},
    "admin": {"sales", "orders", "products", "inventory", "customers", "suppliers", "dashboard", "materials"},
    "production": {"production", "inventory", "products", "materials", "dashboard"},
    "finance": {"finance", "reports", "purchasing", "sales", "dashboard", "expenses", "assets"},
}

def require_module(module: str):
    async def checker(user: dict = Depends(get_current_user)):
        allowed = ROLE_MODULES.get(user["role"], set())
        if "*" in allowed or module in allowed:
            return user
        raise HTTPException(403, f"Access denied for module: {module}")
    return checker

def require_role(*roles: str):
    async def checker(user: dict = Depends(get_current_user)):
        if user["role"] in roles or user["role"] == "owner":
            return user
        raise HTTPException(403, "Insufficient role")
    return checker

# ---------- Audit log ----------
async def audit(user: dict, action: str, entity: str, entity_id: str = "", old: Any = None, new: Any = None):
    await db.audit_logs.insert_one({
        "id": new_id(), "user_id": user["id"], "user_email": user["email"],
        "action": action, "entity": entity, "entity_id": entity_id,
        "old_value": old, "new_value": new, "created_at": now_iso(),
    })

# ---------- AUTH ----------
class LoginIn(BaseModel):
    email: EmailStr
    password: str

@api.post("/auth/login")
async def login(body: LoginIn, response: Response, request: Request):
    email = body.email.lower()
    try:
        user = await db.users.find_one({"email": email})
    except Exception:
        user = None

    if not user:
        user = FALLBACK_USERS.get(email)

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")

    token = create_token(user["id"], user["email"], user["role"])
    secure_cookie = request.url.scheme == "https"
    response.set_cookie("access_token", token, httponly=True, secure=secure_cookie, samesite="none", max_age=604800, path="/")
    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]},
    }

@api.post("/auth/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}

@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user

# ---------- USERS ----------
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str

@api.get("/users", dependencies=[Depends(require_role("owner"))])
async def list_users():
    return await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(500)

@api.post("/users", dependencies=[Depends(require_role("owner"))])
async def create_user(body: UserCreate, user: dict = Depends(get_current_user)):
    if body.role not in ROLE_MODULES:
        raise HTTPException(400, "Invalid role")
    if await db.users.find_one({"email": body.email.lower()}):
        raise HTTPException(400, "Email already exists")
    doc = {
        "id": new_id(), "email": body.email.lower(), "password_hash": hash_password(body.password),
        "name": body.name, "role": body.role, "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    await audit(user, "create", "user", doc["id"], None, {"email": doc["email"], "role": doc["role"]})
    doc.pop("_id", None); doc.pop("password_hash", None)
    return doc

# ---------- Generic CRUD builder ----------
def collection_crud(name: str, module: str):
    """Adds basic list/get/create/update/delete for a MongoDB collection."""
    coll = db[name]

    @api.get(f"/{name}", dependencies=[Depends(require_module(module))])
    async def _list():
        return await coll.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)

    @api.get(f"/{name}/{{item_id}}", dependencies=[Depends(require_module(module))])
    async def _get(item_id: str):
        doc = await coll.find_one({"id": item_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Not found")
        return doc

    @api.post(f"/{name}")
    async def _create(body: Dict[str, Any], user: dict = Depends(require_module(module))):
        body["id"] = body.get("id") or new_id()
        body["created_at"] = now_iso()
        body["updated_at"] = now_iso()
        await coll.insert_one(body)
        await audit(user, "create", name, body["id"], None, body)
        body.pop("_id", None)
        return body

    @api.put(f"/{name}/{{item_id}}")
    async def _update(item_id: str, body: Dict[str, Any], user: dict = Depends(require_module(module))):
        old = await coll.find_one({"id": item_id}, {"_id": 0})
        if not old:
            raise HTTPException(404, "Not found")
        body.pop("id", None); body.pop("_id", None)
        body["updated_at"] = now_iso()
        await coll.update_one({"id": item_id}, {"$set": body})
        new_doc = await coll.find_one({"id": item_id}, {"_id": 0})
        await audit(user, "update", name, item_id, old, new_doc)
        return new_doc

    @api.delete(f"/{name}/{{item_id}}")
    async def _delete(item_id: str, user: dict = Depends(require_module(module))):
        old = await coll.find_one({"id": item_id}, {"_id": 0})
        if not old:
            raise HTTPException(404, "Not found")
        await coll.delete_one({"id": item_id})
        await audit(user, "delete", name, item_id, old, None)
        return {"ok": True}

# Register CRUD for master data
collection_crud("categories", "products")
collection_crud("suppliers", "suppliers")
collection_crud("customers", "customers")
collection_crud("expense_categories", "finance")
collection_crud("marketplaces", "finance")
collection_crud("accounts", "finance")
collection_crud("assets", "assets")
collection_crud("settings_kv", "dashboard")

# ---------- PRODUCTS (with variants) ----------
@api.get("/products", dependencies=[Depends(require_module("products"))])
async def list_products():
    return await db.products.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)

@api.get("/products/{pid}", dependencies=[Depends(require_module("products"))])
async def get_product(pid: str):
    doc = await db.products.find_one({"id": pid}, {"_id": 0})
    if not doc: raise HTTPException(404, "Not found")
    return doc

@api.post("/products")
async def create_product(body: Dict[str, Any], user: dict = Depends(require_module("products"))):
    body["id"] = body.get("id") or new_id()
    body["created_at"] = now_iso()
    body["updated_at"] = now_iso()
    variants = body.get("variants") or []
    for v in variants:
        v["sku"] = v.get("sku") or f"{body.get('sku','SKU')}-{v.get('color','')}-{v.get('size','')}"
        v["stock"] = float(v.get("stock", 0))
        v["cost"] = float(v.get("cost", body.get("cost", 0)))
        v["selling_price"] = float(v.get("selling_price", body.get("selling_price", 0)))
    body["variants"] = variants
    body["status"] = body.get("status", "active")
    await db.products.insert_one(body)
    await audit(user, "create", "product", body["id"], None, body)
    body.pop("_id", None)
    return body

@api.put("/products/{pid}")
async def update_product(pid: str, body: Dict[str, Any], user: dict = Depends(require_module("products"))):
    old = await db.products.find_one({"id": pid}, {"_id": 0})
    if not old: raise HTTPException(404, "Not found")
    body.pop("id", None); body.pop("_id", None)
    body["updated_at"] = now_iso()
    await db.products.update_one({"id": pid}, {"$set": body})
    new_doc = await db.products.find_one({"id": pid}, {"_id": 0})
    await audit(user, "update", "product", pid, old, new_doc)
    return new_doc

@api.delete("/products/{pid}")
async def delete_product(pid: str, user: dict = Depends(require_module("products"))):
    old = await db.products.find_one({"id": pid}, {"_id": 0})
    if not old: raise HTTPException(404, "Not found")
    await db.products.delete_one({"id": pid})
    await audit(user, "delete", "product", pid, old, None)
    return {"ok": True}

# ---------- MATERIALS (raw materials) ----------
collection_crud("materials", "materials")

# ---------- INVENTORY MOVEMENTS ----------
@api.get("/inventory/movements", dependencies=[Depends(require_module("inventory"))])
async def list_movements(limit: int = 500):
    return await db.inventory_movements.find({}, {"_id": 0}).sort("date", -1).to_list(limit)

async def record_movement(kind_ref: str, ref_id: str, ref_type: str, quantity: float, mtype: str, before: float, after: float, user_id: str, notes: str = ""):
    await db.inventory_movements.insert_one({
        "id": new_id(), "target": kind_ref, "ref_id": ref_id, "ref_type": ref_type,
        "type": mtype, "quantity": quantity, "before": before, "after": after,
        "user_id": user_id, "notes": notes, "date": now_iso(),
    })

class MaterialAdjustIn(BaseModel):
    material_id: str
    quantity: float  # can be negative
    type: str = "adjustment"
    notes: str = ""

@api.post("/inventory/materials/adjust")
async def adjust_material(body: MaterialAdjustIn, user: dict = Depends(require_module("inventory"))):
    m = await db.materials.find_one({"id": body.material_id})
    if not m: raise HTTPException(404, "Material not found")
    before = float(m.get("stock", 0))
    after = before + body.quantity
    await db.materials.update_one({"id": body.material_id}, {"$set": {"stock": after, "updated_at": now_iso()}})
    await record_movement("material", body.material_id, "manual", body.quantity, body.type, before, after, user["id"], body.notes)
    return {"ok": True, "before": before, "after": after}

class VariantAdjustIn(BaseModel):
    product_id: str
    variant_sku: str
    quantity: float
    type: str = "adjustment"
    notes: str = ""

@api.post("/inventory/products/adjust")
async def adjust_variant(body: VariantAdjustIn, user: dict = Depends(require_module("inventory"))):
    p = await db.products.find_one({"id": body.product_id})
    if not p: raise HTTPException(404, "Product not found")
    variants = p.get("variants", [])
    for v in variants:
        if v["sku"] == body.variant_sku:
            before = float(v.get("stock", 0))
            v["stock"] = before + body.quantity
            after = v["stock"]
            break
    else:
        raise HTTPException(404, "Variant not found")
    await db.products.update_one({"id": body.product_id}, {"$set": {"variants": variants, "updated_at": now_iso()}})
    await record_movement("product", body.product_id, body.variant_sku, body.quantity, body.type, before, after, user["id"], body.notes)
    return {"ok": True, "before": before, "after": after}

# ---------- BOM ----------
collection_crud("boms", "production")

# ---------- PURCHASING ----------
@api.get("/purchase_orders", dependencies=[Depends(require_module("purchasing"))])
async def list_po():
    return await db.purchase_orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)

@api.post("/purchase_orders")
async def create_po(body: Dict[str, Any], user: dict = Depends(require_module("purchasing"))):
    body["id"] = body.get("id") or new_id()
    body["po_number"] = body.get("po_number") or f"PO-{datetime.now().strftime('%y%m%d')}-{body['id'][:4].upper()}"
    body["status"] = body.get("status", "draft")
    body["received_status"] = body.get("received_status", "pending")
    body["payment_status"] = body.get("payment_status", "unpaid")
    items = body.get("items", [])
    subtotal = sum(float(i.get("quantity", 0)) * float(i.get("unit_cost", 0)) for i in items)
    body["subtotal"] = subtotal
    body["total"] = subtotal - float(body.get("discount", 0)) + float(body.get("shipping", 0)) + float(body.get("tax", 0))
    body["created_at"] = now_iso(); body["updated_at"] = now_iso()
    body["date"] = body.get("date") or now_iso()
    await db.purchase_orders.insert_one(body)
    await audit(user, "create", "purchase_order", body["id"], None, body)
    body.pop("_id", None)
    return body

@api.post("/purchase_orders/{po_id}/receive")
async def receive_po(po_id: str, user: dict = Depends(require_module("purchasing"))):
    po = await db.purchase_orders.find_one({"id": po_id})
    if not po: raise HTTPException(404, "PO not found")
    if po.get("received_status") == "received":
        raise HTTPException(400, "Already received")
    for item in po.get("items", []):
        mid = item.get("material_id")
        qty = float(item.get("quantity", 0))
        if not mid: continue
        m = await db.materials.find_one({"id": mid})
        if not m: continue
        before = float(m.get("stock", 0))
        after = before + qty
        # update weighted average cost
        old_val = before * float(m.get("cost", 0))
        new_val = qty * float(item.get("unit_cost", 0))
        new_cost = (old_val + new_val) / after if after > 0 else float(item.get("unit_cost", 0))
        await db.materials.update_one({"id": mid}, {"$set": {"stock": after, "cost": new_cost, "updated_at": now_iso()}})
        await record_movement("material", mid, po_id, qty, "purchase", before, after, user["id"], f"PO {po['po_number']}")
    await db.purchase_orders.update_one({"id": po_id}, {"$set": {"received_status": "received", "status": "received", "updated_at": now_iso()}})
    # cash entry if paid
    if po.get("payment_status") == "paid":
        await create_financial_transaction(user, "expense", float(po["total"]), po.get("account_id"), f"Purchase {po['po_number']}", "purchase_order", po_id)
    return {"ok": True}

# ---------- PRODUCTION ----------
@api.get("/production_orders", dependencies=[Depends(require_module("production"))])
async def list_prod():
    return await db.production_orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)

@api.post("/production_orders")
async def create_prod(body: Dict[str, Any], user: dict = Depends(require_module("production"))):
    body["id"] = body.get("id") or new_id()
    body["prod_number"] = body.get("prod_number") or f"PROD-{datetime.now().strftime('%y%m%d')}-{body['id'][:4].upper()}"
    body["status"] = body.get("status", "draft")
    body["quantity"] = float(body.get("quantity", 0))
    body["quantity_passed"] = float(body.get("quantity_passed", 0))
    body["quantity_rejected"] = float(body.get("quantity_rejected", 0))
    body["created_at"] = now_iso(); body["updated_at"] = now_iso()
    body["date"] = body.get("date") or now_iso()
    await db.production_orders.insert_one(body)
    await audit(user, "create", "production_order", body["id"], None, body)
    body.pop("_id", None)
    return body

@api.post("/production_orders/{pid}/complete")
async def complete_production(pid: str, body: Dict[str, Any], user: dict = Depends(require_module("production"))):
    po = await db.production_orders.find_one({"id": pid})
    if not po: raise HTTPException(404, "Not found")
    if po.get("status") == "completed":
        raise HTTPException(400, "Already completed")
    qty_passed = float(body.get("quantity_passed", po.get("quantity", 0)))
    qty_rejected = float(body.get("quantity_rejected", 0))
    variant_sku = body.get("variant_sku") or po.get("variant_sku")
    product_id = po.get("product_id")
    bom_items = po.get("bom_items", [])
    total_material_cost = 0.0
    # consume materials
    for bi in bom_items:
        mid = bi["material_id"]; per_unit = float(bi["quantity"])
        needed = per_unit * (qty_passed + qty_rejected)
        m = await db.materials.find_one({"id": mid})
        if not m: continue
        before = float(m.get("stock", 0))
        after = before - needed
        total_material_cost += needed * float(m.get("cost", 0))
        await db.materials.update_one({"id": mid}, {"$set": {"stock": after, "updated_at": now_iso()}})
        await record_movement("material", mid, pid, -needed, "production", before, after, user["id"], f"Prod {po['prod_number']}")
    # add finished goods
    if product_id and variant_sku:
        p = await db.products.find_one({"id": product_id})
        if p:
            variants = p.get("variants", [])
            unit_cost = (total_material_cost / (qty_passed + qty_rejected)) if (qty_passed + qty_rejected) > 0 else 0
            for v in variants:
                if v["sku"] == variant_sku:
                    before = float(v.get("stock", 0))
                    v["stock"] = before + qty_passed
                    after = v["stock"]
                    # weighted avg cost
                    old_val = before * float(v.get("cost", 0))
                    new_val = qty_passed * unit_cost
                    v["cost"] = (old_val + new_val) / after if after > 0 else unit_cost
                    break
            await db.products.update_one({"id": product_id}, {"$set": {"variants": variants, "updated_at": now_iso()}})
            await record_movement("product", product_id, variant_sku, qty_passed, "production", before, after, user["id"], f"Prod {po['prod_number']}")
    await db.production_orders.update_one({"id": pid}, {"$set": {
        "status": "completed", "quantity_passed": qty_passed, "quantity_rejected": qty_rejected,
        "material_cost": total_material_cost, "completed_at": now_iso(), "updated_at": now_iso(),
    }})
    return {"ok": True, "material_cost": total_material_cost}

# ---------- SALES ORDERS ----------
@api.get("/sales_orders", dependencies=[Depends(require_module("sales"))])
async def list_sales():
    return await db.sales_orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)

@api.post("/sales_orders")
async def create_sales(body: Dict[str, Any], user: dict = Depends(require_module("sales"))):
    body["id"] = body.get("id") or new_id()
    body["order_number"] = body.get("order_number") or f"SO-{datetime.now().strftime('%y%m%d')}-{body['id'][:4].upper()}"
    items = body.get("items", [])
    subtotal = 0.0; cogs = 0.0
    # deduct inventory
    for it in items:
        pid = it["product_id"]; vsku = it["variant_sku"]; qty = float(it["quantity"])
        p = await db.products.find_one({"id": pid})
        if not p: raise HTTPException(400, f"Product {pid} not found")
        variants = p.get("variants", [])
        found = False
        for v in variants:
            if v["sku"] == vsku:
                before = float(v.get("stock", 0))
                if before < qty:
                    raise HTTPException(400, f"Insufficient stock for {vsku}")
                v["stock"] = before - qty
                it["cost"] = float(v.get("cost", 0))
                cogs += it["cost"] * qty
                subtotal += float(it["selling_price"]) * qty
                await db.products.update_one({"id": pid}, {"$set": {"variants": variants}})
                await record_movement("product", pid, vsku, -qty, "sales", before, v["stock"], user["id"], f"SO {body['order_number']}")
                found = True
                break
        if not found:
            raise HTTPException(400, f"Variant {vsku} not found")
    discount = float(body.get("discount", 0))
    voucher = float(body.get("voucher", 0))
    shipping = float(body.get("shipping", 0))
    marketplace_fee = float(body.get("marketplace_fee", 0))
    other_fee = float(body.get("other_fee", 0))
    advertising = float(body.get("advertising_cost", 0))
    total = subtotal - discount - voucher + shipping
    net = total - marketplace_fee - other_fee - advertising - cogs
    body.update({
        "subtotal": subtotal, "cogs": cogs, "discount": discount, "voucher": voucher,
        "shipping": shipping, "marketplace_fee": marketplace_fee, "other_fee": other_fee,
        "advertising_cost": advertising, "total": total, "net_profit": net,
        "payment_status": body.get("payment_status", "paid"),
        "fulfillment_status": body.get("fulfillment_status", "processing"),
        "sales_channel": body.get("sales_channel", "Direct"),
        "date": body.get("date") or now_iso(),
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    await db.sales_orders.insert_one(body)
    # financial txn if paid
    if body["payment_status"] == "paid":
        await create_financial_transaction(user, "income", total - marketplace_fee - other_fee, body.get("account_id"), f"Sale {body['order_number']}", "sales_order", body["id"])
    # update customer
    cust_id = body.get("customer_id")
    if cust_id:
        cust = await db.customers.find_one({"id": cust_id})
        if cust:
            total_orders = int(cust.get("total_orders", 0)) + 1
            total_spending = float(cust.get("total_spending", 0)) + total
            ctype = "vip" if total_spending >= 1000000 else ("returning" if total_orders > 1 else "new")
            await db.customers.update_one({"id": cust_id}, {"$set": {
                "total_orders": total_orders, "total_spending": total_spending,
                "last_order": now_iso(), "customer_type": ctype,
            }})
    await audit(user, "create", "sales_order", body["id"], None, body)
    body.pop("_id", None)
    return body

# ---------- FINANCE ----------
async def create_financial_transaction(user, ttype, amount, account_id, description, ref_type, ref_id):
    account_id = account_id or await get_default_account_id()
    txn = {
        "id": new_id(), "type": ttype, "amount": float(amount),
        "account_id": account_id, "description": description,
        "ref_type": ref_type, "ref_id": ref_id, "date": now_iso(),
        "user_id": user["id"], "created_at": now_iso(),
    }
    await db.financial_transactions.insert_one(txn)
    if account_id:
        delta = amount if ttype in ("income", "owner_investment") else -amount
        await db.accounts.update_one({"id": account_id}, {"$inc": {"balance": delta}})

async def get_default_account_id():
    acc = await db.accounts.find_one({"is_default": True}) or await db.accounts.find_one({})
    return acc["id"] if acc else None

@api.get("/financial_transactions", dependencies=[Depends(require_module("finance"))])
async def list_txns():
    return await db.financial_transactions.find({}, {"_id": 0}).sort("date", -1).to_list(1000)

class FinTxnIn(BaseModel):
    type: str  # income/expense/transfer/owner_investment/owner_withdrawal
    amount: float
    account_id: Optional[str] = None
    description: str = ""
    date: Optional[str] = None

@api.post("/financial_transactions")
async def create_txn(body: FinTxnIn, user: dict = Depends(require_module("finance"))):
    await create_financial_transaction(user, body.type, body.amount, body.account_id, body.description, "manual", "")
    return {"ok": True}

# ---------- EXPENSES ----------
@api.get("/expenses", dependencies=[Depends(require_module("finance"))])
async def list_expenses():
    return await db.expenses.find({}, {"_id": 0}).sort("date", -1).to_list(1000)

@api.post("/expenses")
async def create_expense(body: Dict[str, Any], user: dict = Depends(require_module("finance"))):
    body["id"] = body.get("id") or new_id()
    body["created_at"] = now_iso()
    body["date"] = body.get("date") or now_iso()
    body["amount"] = float(body.get("amount", 0))
    await db.expenses.insert_one(body)
    await create_financial_transaction(user, "expense", body["amount"], body.get("account_id"), f"Expense: {body.get('description','')}", "expense", body["id"])
    await audit(user, "create", "expense", body["id"], None, body)
    body.pop("_id", None)
    return body

# ---------- SALES ORDER CANCEL ----------
@api.post("/sales_orders/{sid}/cancel")
async def cancel_sale(sid: str, user: dict = Depends(require_module("sales"))):
    so = await db.sales_orders.find_one({"id": sid})
    if not so:
        raise HTTPException(404, "Order not found")
    if so.get("fulfillment_status") == "cancelled":
        raise HTTPException(400, "Order already cancelled")
    # 1) restore product variant stock
    for it in so.get("items", []):
        p = await db.products.find_one({"id": it["product_id"]})
        if not p:
            continue
        variants = p.get("variants", [])
        for v in variants:
            if v["sku"] == it["variant_sku"]:
                before = float(v.get("stock", 0))
                v["stock"] = before + float(it["quantity"])
                await db.products.update_one({"id": p["id"]}, {"$set": {"variants": variants}})
                await record_movement("product", p["id"], v["sku"], float(it["quantity"]), "return", before, v["stock"], user["id"], f"Cancel {so['order_number']}")
                break
    # 2) reverse financial txn if paid
    prior = await db.financial_transactions.find_one({"ref_type": "sales_order", "ref_id": sid, "type": "income"})
    if prior and not so.get("cancelled_at"):
        await create_financial_transaction(user, "expense", float(prior["amount"]), prior.get("account_id"), f"Refund {so['order_number']}", "sales_cancel", sid)
    # 3) update customer stats (subtract)
    cust_id = so.get("customer_id")
    if cust_id:
        cust = await db.customers.find_one({"id": cust_id})
        if cust:
            new_orders = max(0, int(cust.get("total_orders", 0)) - 1)
            new_spend = max(0, float(cust.get("total_spending", 0)) - float(so.get("total", 0)))
            await db.customers.update_one({"id": cust_id}, {"$set": {"total_orders": new_orders, "total_spending": new_spend}})
    # 4) mark cancelled
    await db.sales_orders.update_one({"id": sid}, {"$set": {"fulfillment_status": "cancelled", "payment_status": "refunded", "cancelled_at": now_iso(), "updated_at": now_iso()}})
    await audit(user, "cancel", "sales_order", sid, so, None)
    return {"ok": True}

# ---------- MARKETPLACE ORDER IMPORT ----------
class ImportOrderIn(BaseModel):
    order_number: Optional[str] = None
    date: Optional[str] = None
    customer_name: Optional[str] = "Marketplace Buyer"
    sales_channel: str = "Shopee"
    variant_sku: str
    quantity: float
    selling_price: float
    discount: Optional[float] = 0
    shipping: Optional[float] = 0
    marketplace_fee: Optional[float] = 0
    advertising_cost: Optional[float] = 0

class BulkImportIn(BaseModel):
    orders: List[ImportOrderIn]

@api.post("/marketplace/import")
async def import_marketplace_orders(body: BulkImportIn, user: dict = Depends(require_module("sales"))):
    created = 0
    skipped = []
    for o in body.orders:
        # find product by variant sku
        p = await db.products.find_one({"variants.sku": o.variant_sku})
        if not p:
            skipped.append({"sku": o.variant_sku, "reason": "Product not found"})
            continue
        v = next((x for x in p["variants"] if x["sku"] == o.variant_sku), None)
        if not v:
            skipped.append({"sku": o.variant_sku, "reason": "Variant not found"})
            continue
        if float(v.get("stock", 0)) < o.quantity:
            skipped.append({"sku": o.variant_sku, "reason": f"Insufficient stock ({v['stock']} available)"})
            continue
        # deduct stock
        before = float(v["stock"])
        v["stock"] = before - o.quantity
        await db.products.update_one({"id": p["id"]}, {"$set": {"variants": p["variants"]}})
        subtotal = o.selling_price * o.quantity
        cogs = float(v.get("cost", 0)) * o.quantity
        total = subtotal - float(o.discount or 0) + float(o.shipping or 0)
        net = total - float(o.marketplace_fee or 0) - float(o.advertising_cost or 0) - cogs
        sid = new_id()
        onum = o.order_number or f"MP-{datetime.now().strftime('%y%m%d')}-{sid[:4].upper()}"
        so = {
            "id": sid, "order_number": onum,
            "date": o.date or now_iso(),
            "customer_name": o.customer_name or "Marketplace Buyer",
            "sales_channel": o.sales_channel,
            "items": [{"product_id": p["id"], "product_name": p["name"], "variant_sku": o.variant_sku, "quantity": o.quantity, "selling_price": o.selling_price, "cost": float(v.get("cost", 0))}],
            "subtotal": subtotal, "cogs": cogs,
            "discount": float(o.discount or 0), "voucher": 0, "shipping": float(o.shipping or 0),
            "marketplace_fee": float(o.marketplace_fee or 0), "other_fee": 0,
            "advertising_cost": float(o.advertising_cost or 0),
            "total": total, "net_profit": net,
            "payment_status": "paid", "fulfillment_status": "completed",
            "imported": True,
            "created_at": now_iso(), "updated_at": now_iso(),
        }
        await db.sales_orders.insert_one(so)
        await record_movement("product", p["id"], o.variant_sku, -o.quantity, "sales", before, v["stock"], user["id"], f"Import {onum}")
        await create_financial_transaction(user, "income", total - float(o.marketplace_fee or 0), await get_default_account_id(), f"Sale {onum} (imported)", "sales_order", sid)
        created += 1
    return {"created": created, "skipped": skipped}

# ---------- ONBOARDING ----------
class OnboardingIn(BaseModel):
    business_name: str
    currency: str = "IDR"
    initial_capital: float = 0
    account_name: str = "Kas Tunai"

@api.post("/onboarding/complete")
async def complete_onboarding(body: OnboardingIn, user: dict = Depends(require_role("owner"))):
    # save business profile
    await db.settings_kv.update_one(
        {"id": "business_profile"},
        {"$set": {"id": "business_profile", "business_name": body.business_name, "currency": body.currency, "setup_complete": True, "updated_at": now_iso()}},
        upsert=True,
    )
    # if capital > 0, seed as owner_investment
    if body.initial_capital > 0:
        # find or create account
        acc = await db.accounts.find_one({"name": body.account_name})
        if not acc:
            acc_id = new_id()
            await db.accounts.insert_one({"id": acc_id, "name": body.account_name, "kind": "cash", "balance": 0, "is_default": True, "created_at": now_iso()})
        else:
            acc_id = acc["id"]
        await create_financial_transaction(user, "owner_investment", body.initial_capital, acc_id, "Initial Capital (Onboarding)", "onboarding", "")
    return {"ok": True}

@api.get("/onboarding/status")
async def onboarding_status(user: dict = Depends(get_current_user)):
    doc = await db.settings_kv.find_one({"id": "business_profile"}, {"_id": 0})
    return {"setup_complete": bool(doc and doc.get("setup_complete")), "profile": doc or {}}

# ---------- REPORT EXPORT ----------
def to_csv(rows: List[Dict], columns: List[str]) -> str:
    import io, csv
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(columns)
    for r in rows:
        w.writerow([r.get(c, "") for c in columns])
    return buf.getvalue()

from fastapi.responses import Response as FastResponse

@api.get("/reports/export/sales")
async def export_sales_csv(user: dict = Depends(require_module("reports"))):
    rows = await db.sales_orders.find({}, {"_id": 0}).sort("date", -1).to_list(10000)
    flat = []
    for r in rows:
        for it in (r.get("items") or [{}]):
            flat.append({
                "order_number": r.get("order_number"),
                "date": r.get("date", "")[:10],
                "customer": r.get("customer_name"),
                "channel": r.get("sales_channel"),
                "product": it.get("product_name"),
                "sku": it.get("variant_sku"),
                "quantity": it.get("quantity"),
                "selling_price": it.get("selling_price"),
                "cost": it.get("cost"),
                "subtotal": r.get("subtotal"),
                "marketplace_fee": r.get("marketplace_fee"),
                "total": r.get("total"),
                "net_profit": r.get("net_profit"),
                "payment_status": r.get("payment_status"),
                "fulfillment_status": r.get("fulfillment_status"),
            })
    csv_text = to_csv(flat, ["order_number","date","customer","channel","product","sku","quantity","selling_price","cost","subtotal","marketplace_fee","total","net_profit","payment_status","fulfillment_status"])
    return FastResponse(content=csv_text, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=sales_export.csv"})

@api.get("/reports/export/inventory")
async def export_inventory_csv(user: dict = Depends(require_module("reports"))):
    products = await db.products.find({}, {"_id": 0}).to_list(10000)
    materials = await db.materials.find({}, {"_id": 0}).to_list(10000)
    flat = []
    for p in products:
        for v in (p.get("variants") or []):
            flat.append({"kind":"product","name":p["name"],"sku":v["sku"],"attributes":f'{v.get("color","")}/{v.get("size","")}',"stock":v.get("stock",0),"cost":v.get("cost",0),"value":float(v.get("stock",0))*float(v.get("cost",0))})
    for m in materials:
        flat.append({"kind":"material","name":m["name"],"sku":"-","attributes":m.get("unit",""),"stock":m.get("stock",0),"cost":m.get("cost",0),"value":float(m.get("stock",0))*float(m.get("cost",0))})
    csv_text = to_csv(flat, ["kind","name","sku","attributes","stock","cost","value"])
    return FastResponse(content=csv_text, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=inventory_export.csv"})

@api.get("/reports/export/profit_loss")
async def export_pl_csv(start: str = "", end: str = "", user: dict = Depends(require_module("reports"))):
    q = {}
    if start: q["date"] = {"$gte": start}
    if end: q.setdefault("date", {})["$lte"] = end
    sales = await db.sales_orders.find(q, {"_id": 0}).to_list(10000)
    expenses = await db.expenses.find(q, {"_id": 0}).to_list(10000)
    revenue = sum(float(s.get("total", 0)) for s in sales)
    cogs = sum(float(s.get("cogs", 0)) for s in sales)
    mp_fees = sum(float(s.get("marketplace_fee", 0)) for s in sales)
    adv = sum(float(s.get("advertising_cost", 0)) for s in sales)
    op_exp = sum(float(e.get("amount", 0)) for e in expenses)
    gp = revenue - cogs
    net = gp - op_exp - mp_fees - adv
    rows = [
        {"line":"Revenue","amount":revenue},
        {"line":"COGS","amount":-cogs},
        {"line":"Gross Profit","amount":gp},
        {"line":"Marketplace Fees","amount":-mp_fees},
        {"line":"Advertising","amount":-adv},
        {"line":"Operating Expenses","amount":-op_exp},
        {"line":"Net Profit","amount":net},
    ]
    return FastResponse(content=to_csv(rows, ["line","amount"]), media_type="text/csv", headers={"Content-Disposition":"attachment; filename=profit_loss.csv"})

# ---------- HPP ENGINE ----------
class HPPComponent(BaseModel):
    label: str
    amount: float

class HPPCalcIn(BaseModel):
    components: List[HPPComponent]
    selling_price: Optional[float] = 0
    marketplace_fee_pct: Optional[float] = 0
    advertising: Optional[float] = 0
    discount: Optional[float] = 0

@api.post("/hpp/calculate", dependencies=[Depends(require_module("dashboard"))])
async def calc_hpp(body: HPPCalcIn):
    hpp = sum(c.amount for c in body.components)
    sp = body.selling_price or 0
    mp_fee = sp * (body.marketplace_fee_pct or 0) / 100
    net_revenue = sp - mp_fee - (body.discount or 0)
    gross_profit = sp - hpp
    net_profit = net_revenue - hpp - (body.advertising or 0)
    margin = (net_profit / sp * 100) if sp else 0
    if margin < 10: health = "too_low"
    elif margin < 25: health = "safe"
    elif margin < 45: health = "healthy"
    else: health = "premium"
    return {
        "hpp": round(hpp, 2), "selling_price": sp, "marketplace_fee": round(mp_fee, 2),
        "gross_profit": round(gross_profit, 2), "net_profit": round(net_profit, 2),
        "margin_percent": round(margin, 2), "health": health,
    }

@api.post("/hpp/simulate", dependencies=[Depends(require_module("dashboard"))])
async def simulate_pricing(body: Dict[str, Any]):
    hpp = float(body.get("hpp", 0))
    mp_pct = float(body.get("marketplace_fee_pct", 0))
    adv = float(body.get("advertising", 0))
    discount = float(body.get("discount", 0))
    prices = body.get("prices") or [69000, 79000, 89000, 99000, 109000, 119000]
    out = []
    for sp in prices:
        sp = float(sp)
        mp_fee = sp * mp_pct / 100
        net = sp - mp_fee - discount - adv - hpp
        margin = (net / sp * 100) if sp else 0
        if margin < 10: health = "too_low"
        elif margin < 25: health = "safe"
        elif margin < 45: health = "healthy"
        else: health = "premium"
        out.append({"price": sp, "revenue": sp, "cost": hpp + mp_fee + adv + discount, "profit": round(net,2), "margin": round(margin,2), "health": health})
    return {"scenarios": out}

# ---------- BEP ----------
@api.post("/bep/calculate", dependencies=[Depends(require_module("dashboard"))])
async def calc_bep(body: Dict[str, Any]):
    fc = float(body.get("fixed_cost", 0))
    vc = float(body.get("variable_cost", 0))
    sp = float(body.get("selling_price", 0))
    cm = sp - vc
    bep_unit = fc / cm if cm > 0 else 0
    bep_rev = bep_unit * sp
    return {"contribution_margin": cm, "bep_unit": round(bep_unit,2), "bep_revenue": round(bep_rev,2)}

# ---------- DASHBOARD ----------
@api.get("/dashboard/kpi", dependencies=[Depends(require_module("dashboard"))])
async def dashboard_kpi(period: str = "month"):
    now = datetime.now(timezone.utc)
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = now - timedelta(days=7)
    elif period == "year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_iso = start.isoformat()

    sales = await db.sales_orders.find({"date": {"$gte": start_iso}}, {"_id": 0}).to_list(10000)
    revenue = sum(float(s.get("total", 0)) for s in sales)
    cogs = sum(float(s.get("cogs", 0)) for s in sales)
    marketplace_fees = sum(float(s.get("marketplace_fee", 0)) for s in sales)
    advertising = sum(float(s.get("advertising_cost", 0)) for s in sales)
    gross_profit = revenue - cogs

    expenses = await db.expenses.find({"date": {"$gte": start_iso}}, {"_id": 0}).to_list(10000)
    op_exp = sum(float(e.get("amount", 0)) for e in expenses)
    net_profit = gross_profit - op_exp - marketplace_fees - advertising

    # inventory value
    products = await db.products.find({}, {"_id": 0}).to_list(10000)
    inv_value = 0
    for p in products:
        for v in p.get("variants", []):
            inv_value += float(v.get("stock", 0)) * float(v.get("cost", 0))
    materials = await db.materials.find({}, {"_id": 0}).to_list(10000)
    for m in materials:
        inv_value += float(m.get("stock", 0)) * float(m.get("cost", 0))

    # cash
    accounts = await db.accounts.find({}, {"_id": 0}).to_list(1000)
    cash = sum(float(a.get("balance", 0)) for a in accounts)

    total_orders = len(sales)

    # low stock alerts
    low_stock = []
    for p in products:
        for v in p.get("variants", []):
            if float(v.get("stock", 0)) <= float(p.get("minimum_stock", 0)) and float(v.get("stock", 0)) > 0:
                low_stock.append({"kind": "product", "name": f"{p['name']} - {v['sku']}", "stock": v["stock"]})
    for m in materials:
        if float(m.get("stock", 0)) <= float(m.get("minimum_stock", 0)):
            low_stock.append({"kind": "material", "name": m["name"], "stock": m["stock"]})

    # health
    health = "healthy"
    if cash < 500000 or net_profit < 0:
        health = "critical"
    elif net_profit < revenue * 0.1:
        health = "warning"

    return {
        "revenue": revenue, "cogs": cogs, "gross_profit": gross_profit,
        "operating_expenses": op_exp, "marketplace_fees": marketplace_fees,
        "advertising": advertising, "net_profit": net_profit,
        "cash_balance": cash, "inventory_value": inv_value,
        "total_orders": total_orders, "low_stock_count": len(low_stock),
        "low_stock_items": low_stock[:10], "health": health, "period": period,
    }

@api.get("/dashboard/charts", dependencies=[Depends(require_module("dashboard"))])
async def dashboard_charts():
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=30)
    sales = await db.sales_orders.find({"date": {"$gte": start.isoformat()}}, {"_id": 0}).to_list(10000)

    # revenue by day
    by_day = {}
    for s in sales:
        d = s["date"][:10]
        by_day.setdefault(d, {"revenue": 0, "profit": 0})
        by_day[d]["revenue"] += float(s.get("total", 0))
        by_day[d]["profit"] += float(s.get("net_profit", 0))
    revenue_chart = [{"date": k, **v} for k, v in sorted(by_day.items())]

    # by product
    by_product = {}
    for s in sales:
        for it in s.get("items", []):
            key = it.get("product_name", it.get("variant_sku", "?"))
            by_product.setdefault(key, {"quantity": 0, "revenue": 0, "profit": 0})
            by_product[key]["quantity"] += float(it.get("quantity", 0))
            by_product[key]["revenue"] += float(it.get("quantity", 0)) * float(it.get("selling_price", 0))
            by_product[key]["profit"] += float(it.get("quantity", 0)) * (float(it.get("selling_price", 0)) - float(it.get("cost", 0)))
    top_products = sorted([{"name": k, **v} for k, v in by_product.items()], key=lambda x: -x["revenue"])[:8]

    # by channel
    by_channel = {}
    for s in sales:
        c = s.get("sales_channel", "Other")
        by_channel[c] = by_channel.get(c, 0) + float(s.get("total", 0))
    channel_chart = [{"channel": k, "value": v} for k, v in by_channel.items()]

    # expenses breakdown
    expenses = await db.expenses.find({"date": {"$gte": start.isoformat()}}, {"_id": 0}).to_list(10000)
    by_cat = {}
    for e in expenses:
        c = e.get("category", "Other")
        by_cat[c] = by_cat.get(c, 0) + float(e.get("amount", 0))
    expense_chart = [{"category": k, "value": v} for k, v in by_cat.items()]

    return {
        "revenue_chart": revenue_chart, "top_products": top_products,
        "channel_chart": channel_chart, "expense_chart": expense_chart,
    }

# ---------- REPORTS ----------
@api.get("/reports/profit_loss", dependencies=[Depends(require_module("reports"))])
async def report_pl(start: str = "", end: str = ""):
    q = {}
    if start: q["date"] = {"$gte": start}
    if end:
        q.setdefault("date", {})["$lte"] = end
    sales = await db.sales_orders.find(q, {"_id": 0}).to_list(10000)
    expenses = await db.expenses.find(q, {"_id": 0}).to_list(10000)
    revenue = sum(float(s.get("total", 0)) for s in sales)
    cogs = sum(float(s.get("cogs", 0)) for s in sales)
    mp_fees = sum(float(s.get("marketplace_fee", 0)) for s in sales)
    adv = sum(float(s.get("advertising_cost", 0)) for s in sales)
    op_exp = sum(float(e.get("amount", 0)) for e in expenses)
    gp = revenue - cogs
    net = gp - op_exp - mp_fees - adv
    return {"revenue": revenue, "cogs": cogs, "gross_profit": gp, "marketplace_fees": mp_fees, "advertising": adv, "operating_expenses": op_exp, "net_profit": net}

# ---------- AUDIT LOG ----------
@api.get("/audit_logs", dependencies=[Depends(require_role("owner"))])
async def list_audit(limit: int = 200):
    return await db.audit_logs.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)

# ---------- SEED ----------
async def seed_all():
    # indexes
    await db.users.create_index("email", unique=True)
    await db.products.create_index("sku")
    await db.materials.create_index("name")

    # owner user
    admin_email = os.environ.get("OWNER_EMAIL", DEFAULT_OWNER_EMAIL).lower()
    admin_password = os.environ.get("OWNER_PASSWORD", DEFAULT_OWNER_PASSWORD)
    admin_name = os.environ.get("OWNER_NAME", "RdCloth Owner")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "id": new_id(), "email": admin_email, "password_hash": hash_password(admin_password),
            "name": admin_name, "role": "owner", "created_at": now_iso(),
        })
        logger.info(f"Created owner: {admin_email}")
    else:
        if not verify_password(admin_password, existing["password_hash"]):
            await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})

    # test users
    for email, pwd, name, role in [
        ("admin@rdcloth.id", "admin123", "Admin Staff", "admin"),
        ("production@rdcloth.id", "production123", "Production Staff", "production"),
        ("finance@rdcloth.id", "finance123", "Finance Staff", "finance"),
    ]:
        if not await db.users.find_one({"email": email}):
            await db.users.insert_one({
                "id": new_id(), "email": email, "password_hash": hash_password(pwd),
                "name": name, "role": role, "created_at": now_iso(),
            })

    # Only seed demo data once
    if await db.products.count_documents({}) > 0:
        return

    logger.info("Seeding demo data...")

    # accounts
    cash_id = new_id(); bank_id = new_id(); mp_id = new_id()
    await db.accounts.insert_many([
        {"id": cash_id, "name": "Kas Tunai", "kind": "cash", "balance": 0, "is_default": True, "created_at": now_iso()},
        {"id": bank_id, "name": "Bank BCA", "kind": "bank", "balance": 0, "created_at": now_iso()},
        {"id": mp_id, "name": "Shopee Balance", "kind": "marketplace", "balance": 0, "created_at": now_iso()},
    ])

    # marketplaces
    await db.marketplaces.insert_many([
        {"id": new_id(), "name": "Shopee", "admin_fee_pct": 4.25, "service_fee_pct": 4.5, "payment_fee_pct": 1.5, "advertising_fee_pct": 0, "created_at": now_iso()},
        {"id": new_id(), "name": "TikTok Shop", "admin_fee_pct": 4.5, "service_fee_pct": 3.5, "payment_fee_pct": 1.5, "advertising_fee_pct": 0, "created_at": now_iso()},
        {"id": new_id(), "name": "WhatsApp", "admin_fee_pct": 0, "service_fee_pct": 0, "payment_fee_pct": 0, "advertising_fee_pct": 0, "created_at": now_iso()},
        {"id": new_id(), "name": "Direct/Offline", "admin_fee_pct": 0, "service_fee_pct": 0, "payment_fee_pct": 0, "advertising_fee_pct": 0, "created_at": now_iso()},
    ])

    # categories
    cat_shirt = new_id(); cat_bag = new_id(); cat_cap = new_id()
    await db.categories.insert_many([
        {"id": cat_shirt, "name": "T-Shirt", "kind": "product", "created_at": now_iso()},
        {"id": cat_bag, "name": "Tote Bag", "kind": "product", "created_at": now_iso()},
        {"id": cat_cap, "name": "Cap", "kind": "product", "created_at": now_iso()},
    ])

    # expense categories
    for name in ["Advertising", "Electricity", "Internet", "Packaging", "Transportation", "Software", "Marketplace", "Office", "Other"]:
        await db.expense_categories.insert_one({"id": new_id(), "name": name, "created_at": now_iso()})

    # suppliers
    sup_shirt = new_id(); sup_dtf = new_id(); sup_pack = new_id()
    await db.suppliers.insert_many([
        {"id": sup_shirt, "name": "Supplier Kaos Bandung", "contact": "Pak Ahmad", "phone": "081234567890", "email": "kaos@supplier.id", "address": "Bandung", "lead_time_days": 3, "created_at": now_iso()},
        {"id": sup_dtf, "name": "Vendor DTF Jakarta", "contact": "Bu Sari", "phone": "082345678901", "email": "dtf@vendor.id", "address": "Jakarta", "lead_time_days": 2, "created_at": now_iso()},
        {"id": sup_pack, "name": "Toko Packaging", "contact": "Pak Budi", "phone": "083456789012", "email": "pack@toko.id", "address": "Surabaya", "lead_time_days": 1, "created_at": now_iso()},
    ])

    # customers
    for name, phone, ctype in [
        ("Rina Sari", "081111111111", "vip"),
        ("Budi Santoso", "082222222222", "returning"),
        ("Andi Wijaya", "083333333333", "new"),
    ]:
        await db.customers.insert_one({"id": new_id(), "name": name, "phone": phone, "customer_type": ctype, "total_orders": 0, "total_spending": 0, "created_at": now_iso()})

    # materials
    mat_shirt_black = new_id(); mat_shirt_white = new_id()
    mat_dtf = new_id(); mat_pack = new_id(); mat_sticker = new_id(); mat_tag = new_id(); mat_card = new_id()
    mat_tote = new_id(); mat_cap = new_id()
    await db.materials.insert_many([
        {"id": mat_shirt_black, "name": "Kaos Polos Hitam", "unit": "pcs", "stock": 50, "cost": 30000, "minimum_stock": 10, "supplier_id": sup_shirt, "created_at": now_iso()},
        {"id": mat_shirt_white, "name": "Kaos Polos Putih", "unit": "pcs", "stock": 50, "cost": 30000, "minimum_stock": 10, "supplier_id": sup_shirt, "created_at": now_iso()},
        {"id": mat_dtf, "name": "DTF Transfer A4", "unit": "pcs", "stock": 100, "cost": 15000, "minimum_stock": 20, "supplier_id": sup_dtf, "created_at": now_iso()},
        {"id": mat_pack, "name": "Packaging Box", "unit": "pcs", "stock": 200, "cost": 4000, "minimum_stock": 30, "supplier_id": sup_pack, "created_at": now_iso()},
        {"id": mat_sticker, "name": "Sticker RdCloth", "unit": "pcs", "stock": 500, "cost": 1500, "minimum_stock": 50, "supplier_id": sup_pack, "created_at": now_iso()},
        {"id": mat_tag, "name": "Hang Tag", "unit": "pcs", "stock": 500, "cost": 500, "minimum_stock": 50, "supplier_id": sup_pack, "created_at": now_iso()},
        {"id": mat_card, "name": "Thank You Card", "unit": "pcs", "stock": 500, "cost": 500, "minimum_stock": 50, "supplier_id": sup_pack, "created_at": now_iso()},
        {"id": mat_tote, "name": "Totebag Canvas Polos", "unit": "pcs", "stock": 30, "cost": 25000, "minimum_stock": 5, "supplier_id": sup_shirt, "created_at": now_iso()},
        {"id": mat_cap, "name": "Topi Polos", "unit": "pcs", "stock": 20, "cost": 35000, "minimum_stock": 5, "supplier_id": sup_shirt, "created_at": now_iso()},
    ])

    # products
    def variants(sku_base, colors, sizes, cost, price, stocks=None):
        arr = []
        i = 0
        for c in colors:
            for s in sizes:
                arr.append({
                    "sku": f"{sku_base}-{c[:2].upper()}-{s}",
                    "color": c, "size": s, "cost": cost, "selling_price": price,
                    "stock": (stocks[i] if stocks else 5),
                })
                i += 1
        return arr

    products = [
        {"id": new_id(), "sku": "RDB", "name": "RdBasic T-Shirt", "category_id": cat_shirt, "brand": "RdCloth", "material": "Cotton Combed 30s", "image_url": "https://images.pexels.com/photos/8532616/pexels-photo-8532616.jpeg",
         "cost": 54500, "selling_price": 89000, "minimum_stock": 3, "status": "active",
         "variants": variants("RDB", ["Black","White"], ["S","M","L","XL"], 54500, 89000, [8,12,10,5, 6,8,7,4])},
        {"id": new_id(), "sku": "RDC", "name": "RdCustom T-Shirt", "category_id": cat_shirt, "brand": "RdCloth", "material": "Cotton Combed 30s", "image_url": "https://images.pexels.com/photos/12025472/pexels-photo-12025472.jpeg",
         "cost": 54500, "selling_price": 109000, "minimum_stock": 3, "status": "active",
         "variants": variants("RDC", ["Black","White"], ["S","M","L","XL"], 54500, 109000, [4,6,5,3, 3,5,4,2])},
        {"id": new_id(), "sku": "RDT", "name": "RdTote Canvas", "category_id": cat_bag, "brand": "RdCloth", "material": "Canvas Blacu",  "image_url": "https://images.unsplash.com/photo-1544816155-12df9643f363",
         "cost": 42000, "selling_price": 79000, "minimum_stock": 3, "status": "active",
         "variants": variants("RDT", ["Natural"], ["OS"], 42000, 79000, [15])},
        {"id": new_id(), "sku": "RDP", "name": "RdCap Snapback", "category_id": cat_cap, "brand": "RdCloth", "material": "Twill",
         "cost": 47000, "selling_price": 95000, "minimum_stock": 2, "status": "active",
         "variants": variants("RDP", ["Black"], ["OS"], 47000, 95000, [8])},
    ]
    for p in products:
        p["created_at"] = now_iso()
    await db.products.insert_many(products)

    # BOM
    bom_items = [
        {"material_id": mat_shirt_black, "material_name": "Kaos Polos Hitam", "quantity": 1},
        {"material_id": mat_dtf, "material_name": "DTF Transfer", "quantity": 1},
        {"material_id": mat_pack, "material_name": "Packaging Box", "quantity": 1},
        {"material_id": mat_sticker, "material_name": "Sticker RdCloth", "quantity": 1},
        {"material_id": mat_tag, "material_name": "Hang Tag", "quantity": 1},
        {"material_id": mat_card, "material_name": "Thank You Card", "quantity": 1},
    ]
    await db.boms.insert_one({
        "id": new_id(), "product_id": products[0]["id"], "product_name": products[0]["name"],
        "items": bom_items, "created_at": now_iso(),
    })

    # Owner initial capital
    await db.financial_transactions.insert_one({
        "id": new_id(), "type": "owner_investment", "amount": 4000000,
        "account_id": cash_id, "description": "Initial Capital (DEMO)",
        "ref_type": "manual", "ref_id": "", "date": now_iso(), "created_at": now_iso(),
    })
    await db.accounts.update_one({"id": cash_id}, {"$inc": {"balance": 4000000}})

    # Sample sales
    owner = await db.users.find_one({"role": "owner"})
    channels = ["Shopee", "TikTok Shop", "WhatsApp", "Direct/Offline"]
    customers = await db.customers.find({}).to_list(10)
    for i in range(15):
        p = products[i % len(products)]
        v = p["variants"][i % len(p["variants"])]
        qty = (i % 3) + 1
        channel = channels[i % 4]
        mp_pct = 8.75 if channel == "Shopee" else (8.0 if channel == "TikTok Shop" else 0)
        sp = float(v["selling_price"])
        subtotal = sp * qty
        mp_fee = subtotal * mp_pct / 100
        cogs = float(v["cost"]) * qty
        adv = 3000 * qty if channel in ("Shopee","TikTok Shop") else 0
        total = subtotal
        # deduct stock
        v["stock"] = max(0, v["stock"] - qty)
        d = (datetime.now(timezone.utc) - timedelta(days=i)).isoformat()
        so_id = new_id()
        await db.sales_orders.insert_one({
            "id": so_id, "order_number": f"SO-DEMO-{i+1:03d}",
            "date": d, "customer_id": customers[i % len(customers)]["id"],
            "customer_name": customers[i % len(customers)]["name"],
            "sales_channel": channel,
            "items": [{"product_id": p["id"], "product_name": p["name"], "variant_sku": v["sku"], "quantity": qty, "selling_price": sp, "cost": float(v["cost"])}],
            "subtotal": subtotal, "cogs": cogs, "discount": 0, "voucher": 0, "shipping": 0,
            "marketplace_fee": mp_fee, "other_fee": 0, "advertising_cost": adv,
            "total": total, "net_profit": total - cogs - mp_fee - adv,
            "payment_status": "paid", "fulfillment_status": "completed",
            "created_at": d, "updated_at": d,
        })
    # update product variants stocks
    for p in products:
        await db.products.update_one({"id": p["id"]}, {"$set": {"variants": p["variants"]}})

    # sample expenses
    for name, amt, cat in [("Listrik Bulanan", 350000, "Electricity"), ("Internet", 400000, "Internet"), ("Iklan Shopee", 200000, "Advertising")]:
        d = datetime.now(timezone.utc).isoformat()
        exp_id = new_id()
        await db.expenses.insert_one({"id": exp_id, "date": d, "category": cat, "description": name, "amount": amt, "account_id": cash_id, "created_at": d})
        await db.accounts.update_one({"id": cash_id}, {"$inc": {"balance": -amt}})
        await db.financial_transactions.insert_one({"id": new_id(), "type": "expense", "amount": amt, "account_id": cash_id, "description": name, "ref_type": "expense", "ref_id": exp_id, "date": d, "created_at": d})

    # asset
    await db.assets.insert_one({
        "id": new_id(), "name": "Heat Press Machine", "purchase_price": 1500000, "purchase_date": (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()[:10],
        "useful_life_years": 5, "residual_value": 0, "created_at": now_iso(),
    })

    logger.info("Demo data seeded.")

@app.on_event("startup")
async def _startup():
    # Allow skipping demo data seeding when MongoDB isn't available or during quick dev runs
    if os.environ.get("SKIP_DEMO_SEED", "").lower() in ("1", "true", "yes"):
        logger.info("SKIP_DEMO_SEED is set; skipping demo data seeding on startup")
        return
    try:
        await seed_all()
    except Exception as e:
        logger.exception(f"Seed error: {e}")

@app.on_event("shutdown")
async def _shutdown():
    client.close()

@api.get("/")
async def root():
    return {"app": "RdCloth ERP", "status": "ok"}

app.include_router(api)
