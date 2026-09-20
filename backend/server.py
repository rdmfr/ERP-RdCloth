from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
import math
import contextvars
import re
import shutil
from contextlib import asynccontextmanager
from functools import wraps
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
import io
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# ---------- Config ----------
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']
JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALG = "HS256"
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").lower()
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() in ("1", "true", "yes")
if ENVIRONMENT == "production" and len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must contain at least 32 characters in production")
if ENVIRONMENT == "production" and DEMO_MODE:
    raise RuntimeError("DEMO_MODE must be disabled in production")

use_mock = os.environ.get("USE_MOCK_DB", "").lower() in ("1", "true", "yes")
if not use_mock:
    try:
        from pymongo import MongoClient
        test_client = MongoClient(
            MONGO_URL,
            serverSelectionTimeoutMS=int(os.environ.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", "10000")),
            connectTimeoutMS=int(os.environ.get("MONGO_CONNECT_TIMEOUT_MS", "10000")),
        )
        test_client.admin.command('ping')
        test_client.close()
        client = AsyncIOMotorClient(
            MONGO_URL,
            serverSelectionTimeoutMS=int(os.environ.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", "1500")),
            connectTimeoutMS=int(os.environ.get("MONGO_CONNECT_TIMEOUT_MS", "1500")),
        )
    except Exception:
        if MONGO_URL.startswith("mongodb+srv://"):
            raise
        use_mock = True

if use_mock:
    import mongomock_motor
    client = mongomock_motor.AsyncMongoMockClient()

db = client[DB_NAME]

_mongo_session = contextvars.ContextVar("mongo_session", default=None)

class _SessionCollection:
    def __init__(self, collection):
        self._collection = collection

    def __getattr__(self, name):
        operation = getattr(self._collection, name)
        if name in {"find", "find_one", "insert_one", "insert_many", "update_one", "update_many", "delete_one", "count_documents", "create_index"}:
            def with_session(*args, **kwargs):
                session = _mongo_session.get()
                if session is not None:
                    kwargs.setdefault("session", session)
                return operation(*args, **kwargs)
            return with_session
        return operation

class _SessionDatabase:
    def __init__(self, database):
        self._database = database

    def __getitem__(self, name):
        return _SessionCollection(self._database[name])

    def __getattr__(self, name):
        return getattr(self._database, name)

db = _SessionDatabase(client[DB_NAME])
ATTACHMENTS_DIR = Path(os.environ.get("ATTACHMENTS_DIR", "D:/NexaBiz"))
ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR = Path(os.environ.get("BACKUPS_DIR", str(ATTACHMENTS_DIR.parent / "backups")))

@asynccontextmanager
async def mongo_transaction():
    if use_mock:
        yield
        return
    session = await client.start_session()
    token = _mongo_session.set(session)
    try:
        async with session.start_transaction():
            yield
    finally:
        _mongo_session.reset(token)
        await session.end_session()

def transactional(handler):
    @wraps(handler)
    async def wrapped(*args, **kwargs):
        async with mongo_transaction():
            return await handler(*args, **kwargs)
    return wrapped

app = FastAPI(title="NexaBiz ERP API", description="Self-hosted ERP template for small businesses")
api = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nexabiz")

# ---------- Helpers ----------
def new_id() -> str:
    return str(uuid.uuid4())

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def json_safe(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value

def nonnegative(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise HTTPException(400, f"{field} must be a number")
    if not math.isfinite(number) or number < 0:
        raise HTTPException(400, f"{field} must be non-negative")
    return number

def positive(value: Any, field: str) -> float:
    number = nonnegative(value, field)
    if number <= 0:
        raise HTTPException(400, f"{field} must be greater than zero")
    return number

def hash_password(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()

DEFAULT_OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "owner@example.com").lower()
DEFAULT_OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "change-this-demo-password")

FALLBACK_USERS = {
    DEFAULT_OWNER_EMAIL: {
        "id": "owner-demo", "email": DEFAULT_OWNER_EMAIL, "name": "NexaBiz Owner", "role": "owner",
        "password_hash": hash_password(DEFAULT_OWNER_PASSWORD),
    },
    "admin@example.com": {
        "id": "admin-demo", "email": "admin@example.com", "name": "Admin Staff", "role": "admin",
        "password_hash": hash_password("admin123"),
    },
    "production@example.com": {
        "id": "production-demo", "email": "production@example.com", "name": "Production Staff", "role": "production",
        "password_hash": hash_password("production123"),
    },
    "finance@example.com": {
        "id": "finance-demo", "email": "finance@example.com", "name": "Finance Staff", "role": "finance",
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
    "admin": {"sales", "orders", "products", "inventory", "customers", "suppliers", "dashboard", "materials", "crm"},
    "production": {"production", "inventory", "products", "materials", "dashboard"},
    "finance": {"finance", "reports", "purchasing", "sales", "dashboard", "expenses", "assets", "crm"},
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
        "old_value": json_safe(old), "new_value": json_safe(new), "created_at": now_iso(),
    })

@api.post("/attachments")
async def upload_attachment(
    file: UploadFile = File(...), entity_type: str = Form(...), entity_id: str = Form(...),
    user: dict = Depends(get_current_user),
):
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", entity_type) or not entity_id:
        raise HTTPException(400, "Invalid attachment reference")
    original_name = Path(file.filename or "attachment").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".csv", ".xlsx", ".doc", ".docx"}:
        raise HTTPException(400, "Unsupported attachment type")
    max_size = int(os.environ.get("MAX_ATTACHMENT_SIZE_MB", "10")) * 1024 * 1024
    if file.size and file.size > max_size:
        raise HTTPException(413, "Attachment exceeds the configured size limit")
    attachment_id = new_id()
    stored_name = f"{attachment_id}{suffix}"
    target = ATTACHMENTS_DIR / stored_name
    with target.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    doc = {"id": attachment_id, "entity_type": entity_type, "entity_id": entity_id, "original_name": original_name, "stored_name": stored_name, "content_type": file.content_type or "application/octet-stream", "size": target.stat().st_size, "uploaded_by": user["id"], "created_at": now_iso()}
    await db.attachments.insert_one(doc)
    await audit(user, "upload", "attachment", attachment_id, None, {k: v for k, v in doc.items() if k != "stored_name"})
    doc.pop("_id", None)
    return doc

@api.get("/attachments")
async def list_attachments(entity_type: str, entity_id: str, user: dict = Depends(get_current_user)):
    return await db.attachments.find({"entity_type": entity_type, "entity_id": entity_id}, {"_id": 0, "stored_name": 0}).sort("created_at", -1).to_list(100)

@api.get("/attachments/{attachment_id}/download")
async def download_attachment(attachment_id: str, user: dict = Depends(get_current_user)):
    attachment = await db.attachments.find_one({"id": attachment_id}, {"_id": 0})
    if not attachment:
        raise HTTPException(404, "Attachment not found")
    target = ATTACHMENTS_DIR / attachment["stored_name"]
    if not target.is_file():
        raise HTTPException(404, "Attachment file not found")
    return FileResponse(target, media_type=attachment.get("content_type"), filename=attachment.get("original_name", target.name))

# ---------- AUTH & SECURITY HARDENING ----------
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

def validate_password_strength(password: str) -> None:
    if not password or len(password) < 8:
        raise HTTPException(400, "Password minimal harus 8 karakter.")
    if not any(c.isdigit() for c in password):
        raise HTTPException(400, "Password harus mengandung minimal satu angka (0-9).")
    if not any(c.isalpha() for c in password):
        raise HTTPException(400, "Password harus mengandung minimal satu huruf (a-z, A-Z).")

async def check_login_rate_limit(email: str, ip: str) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
    attempts = await db.login_attempts.count_documents({
        "$or": [{"email": email}, {"ip": ip}],
        "timestamp": {"$gte": cutoff},
        "success": False
    })
    if attempts >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Terlalu banyak percobaan login gagal. Akun/IP terkunci sementara selama {LOCKOUT_MINUTES} menit."
        )

async def record_login_attempt(email: str, ip: str, success: bool) -> None:
    doc = {
        "id": new_id(),
        "email": email,
        "ip": ip,
        "success": success,
        "timestamp": now_iso()
    }
    await db.login_attempts.insert_one(doc)
    if success:
        await db.login_attempts.delete_many({
            "$or": [{"email": email}, {"ip": ip}],
            "success": False
        })

class LoginIn(BaseModel):
    email: EmailStr
    password: str

@api.post("/auth/login")
async def login(body: LoginIn, response: Response, request: Request):
    email = body.email.lower()
    client_ip = request.client.host if request.client else "127.0.0.1"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
        
    await check_login_rate_limit(email, client_ip)
    
    try:
        user = await db.users.find_one({"email": email})
    except Exception:
        user = None

    if not user and ENVIRONMENT != "production" and DEMO_MODE:
        user = FALLBACK_USERS.get(email)

    if not user or not verify_password(body.password, user["password_hash"]):
        await record_login_attempt(email, client_ip, success=False)
        await audit({"id": "system", "email": email, "role": "anonymous"}, "login_failed", "auth", email, None, {"ip": client_ip, "reason": "Invalid credentials"})
        raise HTTPException(401, "Email atau password salah")

    if user.get("status") in ("inactive", "archived", "disabled"):
        await record_login_attempt(email, client_ip, success=False)
        raise HTTPException(403, "Akun Anda telah dinonaktifkan. Silakan hubungi Administrator.")

    await record_login_attempt(email, client_ip, success=True)
    await audit({"id": user["id"], "email": user["email"], "role": user["role"]}, "login_success", "auth", user["id"], None, {"ip": client_ip})

    token = create_token(user["id"], user["email"], user["role"])
    secure_cookie = request.url.scheme == "https"
    response.set_cookie("access_token", token, httponly=True, secure=secure_cookie, samesite="none", max_age=604800, path="/")
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "status": user.get("status", "active"),
        },
    }

@api.post("/auth/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}

@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user

class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str

@api.post("/auth/change-password")
async def change_password(body: ChangePasswordIn, user: dict = Depends(get_current_user)):
    db_user = await db.users.find_one({"id": user["id"]})
    if not db_user:
        raise HTTPException(404, "User tidak ditemukan")
    if not verify_password(body.current_password, db_user["password_hash"]):
        raise HTTPException(400, "Password saat ini tidak cocok")
    validate_password_strength(body.new_password)
    new_hash = hash_password(body.new_password)
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": new_hash, "updated_at": now_iso()}})
    await audit(user, "change_password", "user", user["id"], None, {"email": user["email"]})
    return {"ok": True, "message": "Password berhasil diubah"}

# ---------- USERS & ROLE MANAGEMENT ----------
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str

@api.get("/users", dependencies=[Depends(require_role("owner"))])
async def list_users():
    return await db.users.find({"status": {"$ne": "archived"}}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(500)

@api.post("/users", dependencies=[Depends(require_role("owner"))])
async def create_user(body: UserCreate, user: dict = Depends(get_current_user)):
    if body.role not in ROLE_MODULES:
        raise HTTPException(400, "Role tidak valid")
    validate_password_strength(body.password)
    if await db.users.find_one({"email": body.email.lower()}):
        raise HTTPException(400, "Email sudah terdaftar")
    doc = {
        "id": new_id(), "email": body.email.lower(), "password_hash": hash_password(body.password),
        "name": body.name, "role": body.role, "status": "active", "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.users.insert_one(doc)
    await audit(user, "create", "user", doc["id"], None, {"email": doc["email"], "role": doc["role"]})
    doc.pop("_id", None); doc.pop("password_hash", None)
    return doc

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None # active / inactive

@api.put("/users/{user_id}", dependencies=[Depends(require_role("owner"))])
async def update_user(user_id: str, body: UserUpdate, user: dict = Depends(get_current_user)):
    existing = await db.users.find_one({"id": user_id})
    if not existing:
        raise HTTPException(404, "User tidak ditemukan")
    if body.role and body.role not in ROLE_MODULES:
        raise HTTPException(400, "Role tidak valid")
    if existing["role"] == "owner" and body.role and body.role != "owner":
        other_owners = await db.users.count_documents({"role": "owner", "id": {"$ne": user_id}, "status": {"$ne": "archived"}})
        if other_owners == 0:
            raise HTTPException(400, "Sistem harus memiliki minimal satu akun Owner aktif.")
            
    updates = {"updated_at": now_iso()}
    if body.name is not None:
        updates["name"] = body.name
    if body.role is not None:
        updates["role"] = body.role
    if body.status is not None:
        if existing["id"] == user["id"] and body.status == "inactive":
            raise HTTPException(400, "Anda tidak dapat menonaktifkan akun Anda sendiri.")
        updates["status"] = body.status
        
    await db.users.update_one({"id": user_id}, {"$set": updates})
    new_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    await audit(user, "update", "user", user_id, {"name": existing.get("name"), "role": existing.get("role"), "status": existing.get("status")}, new_doc)
    return new_doc

class ResetPasswordIn(BaseModel):
    new_password: str

@api.post("/users/{user_id}/reset-password", dependencies=[Depends(require_role("owner"))])
async def reset_user_password(user_id: str, body: ResetPasswordIn, user: dict = Depends(get_current_user)):
    existing = await db.users.find_one({"id": user_id})
    if not existing:
        raise HTTPException(404, "User tidak ditemukan")
    validate_password_strength(body.new_password)
    new_hash = hash_password(body.new_password)
    await db.users.update_one({"id": user_id}, {"$set": {"password_hash": new_hash, "updated_at": now_iso()}})
    await audit(user, "reset_password", "user", user_id, None, {"email": existing["email"]})
    return {"ok": True, "message": f"Password untuk {existing['email']} berhasil di-reset"}

@api.delete("/users/{user_id}", dependencies=[Depends(require_role("owner"))])
async def delete_user(user_id: str, user: dict = Depends(get_current_user)):
    existing = await db.users.find_one({"id": user_id})
    if not existing:
        raise HTTPException(404, "User tidak ditemukan")
    if existing["id"] == user["id"]:
        raise HTTPException(400, "Anda tidak dapat menghapus akun Anda sendiri.")
    if existing["role"] == "owner":
        other_owners = await db.users.count_documents({"role": "owner", "id": {"$ne": user_id}, "status": {"$ne": "archived"}})
        if other_owners == 0:
            raise HTTPException(400, "Tidak dapat menghapus satu-satunya akun Owner.")
            
    await db.users.update_one({"id": user_id}, {"$set": {"status": "archived", "archived_at": now_iso(), "updated_at": now_iso()}})
    await audit(user, "archive", "user", user_id, None, {"email": existing["email"]})
    return {"ok": True, "archived": True}

# ---------- Generic CRUD builder ----------
def collection_crud(name: str, module: str):
    """Adds basic list/get/create/update/delete for a MongoDB collection."""
    coll = db[name]

    @api.get(f"/{name}", dependencies=[Depends(require_module(module))])
    async def _list():
        sort_field = [("code", 1), ("created_at", 1)] if name == "accounts" else [("created_at", -1)]
        return await coll.find({"status": {"$ne": "archived"}}, {"_id": 0}).sort(sort_field).to_list(1000)

    @api.get(f"/{name}/{{item_id}}", dependencies=[Depends(require_module(module))])
    async def _get(item_id: str):
        doc = await coll.find_one({"id": item_id, "status": {"$ne": "archived"}}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Not found")
        return doc

    @api.post(f"/{name}")
    async def _create(body: Dict[str, Any], user: dict = Depends(require_module(module))):
        body["id"] = body.get("id") or new_id()
        body["created_at"] = now_iso()
        body["updated_at"] = now_iso()
        purchase_payment_status = body.pop("purchase_payment_status", "unpaid") if name == "materials" else "unpaid"
        purchase_account_id = body.pop("purchase_account_id", None) if name == "materials" else None
        purchase_amount = 0
        if name == "materials" and purchase_payment_status == "paid":
            purchase_amount = nonnegative(body.get("stock", 0), "Initial stock") * nonnegative(body.get("cost", 0), "Material cost")
        await coll.insert_one(body)
        if name in {"invoices", "bills"} and float(body.get("amount", 0)) > 0:
            await create_document_journal(user, name, body)
        if name == "materials" and purchase_amount > 0:
            await create_financial_transaction(
                user, "expense", purchase_amount, purchase_account_id,
                f"Pembelian bahan {body.get('name', '')}", "material_purchase", body["id"],
            )
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
        if name == "accounts" and old.get("is_system"):
            raise HTTPException(400, "Akun sistem inti tidak dapat dihapus.")
        archived_at = now_iso()
        await coll.update_one({"id": item_id}, {"$set": {"status": "archived", "archived_at": archived_at, "updated_at": archived_at}})
        archived = await coll.find_one({"id": item_id}, {"_id": 0})
        await audit(user, "archive", name, item_id, old, archived)
        return {"ok": True, "archived": True}

# Register CRUD for master data
collection_crud("categories", "products")
collection_crud("suppliers", "suppliers")
collection_crud("customers", "customers")
collection_crud("expense_categories", "finance")
collection_crud("marketplaces", "finance")
collection_crud("accounts", "finance")
collection_crud("assets", "assets")
collection_crud("settings_kv", "dashboard")
collection_crud("invoices", "finance")
collection_crud("bills", "finance")
collection_crud("crm_activities", "crm")

# ---------- PRODUCTS (with variants) ----------
@api.get("/products", dependencies=[Depends(require_module("products"))])
async def list_products():
    return await db.products.find({"status": {"$ne": "archived"}}, {"_id": 0}).sort("created_at", -1).to_list(1000)

@api.get("/products/{pid}", dependencies=[Depends(require_module("products"))])
async def get_product(pid: str):
    doc = await db.products.find_one({"id": pid, "status": {"$ne": "archived"}}, {"_id": 0})
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
    archived_at = now_iso()
    await db.products.update_one({"id": pid}, {"$set": {"status": "archived", "archived_at": archived_at, "updated_at": archived_at}})
    archived = await db.products.find_one({"id": pid}, {"_id": 0})
    await audit(user, "archive", "product", pid, old, archived)
    return {"ok": True, "archived": True}

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
    if not math.isfinite(body.quantity) or after < 0:
        raise HTTPException(400, "Stock cannot be negative")
    await db.materials.update_one({"id": body.material_id}, {"$set": {"stock": after, "updated_at": now_iso()}})
    await record_movement("material", body.material_id, "manual", body.quantity, body.type, before, after, user["id"], body.notes)
    return {"ok": True, "before": before, "after": after}

class VariantAdjustIn(BaseModel):
    product_id: str
    variant_sku: str
    quantity: float
    type: str = "adjustment"
    notes: str = ""

class BulkAdjustmentIn(BaseModel):
    adjustments: List[VariantAdjustIn | MaterialAdjustIn]

@api.post("/inventory/bulk-adjust")
@transactional
async def bulk_adjust_inventory(body: BulkAdjustmentIn, user: dict = Depends(require_module("inventory"))):
    if not body.adjustments:
        raise HTTPException(400, "At least one adjustment is required")
    results = []
    for adjustment in body.adjustments:
        if isinstance(adjustment, MaterialAdjustIn):
            result = await adjust_material(adjustment, user)
        else:
            result = await adjust_variant(adjustment, user)
        results.append(result)
    return {"ok": True, "count": len(results), "results": results}

class StockOpnameIn(BaseModel):
    kind: str
    item_id: str
    variant_sku: Optional[str] = None
    physical_stock: float
    notes: str = ""

@api.post("/inventory/opname")
@transactional
async def stock_opname(body: StockOpnameIn, user: dict = Depends(require_module("inventory"))):
    physical = nonnegative(body.physical_stock, "Physical stock")
    if body.kind == "material":
        item = await db.materials.find_one({"id": body.item_id})
        if not item:
            raise HTTPException(404, "Material not found")
        before = float(item.get("stock", 0))
        await db.materials.update_one({"id": body.item_id}, {"$set": {"stock": physical, "updated_at": now_iso()}})
        target = body.item_id
    elif body.kind == "product":
        if not body.variant_sku:
            raise HTTPException(400, "Variant SKU is required")
        item = await db.products.find_one({"id": body.item_id})
        if not item:
            raise HTTPException(404, "Product not found")
        variants = item.get("variants", [])
        variant = next((value for value in variants if value.get("sku") == body.variant_sku), None)
        if not variant:
            raise HTTPException(404, "Variant not found")
        before = float(variant.get("stock", 0))
        variant["stock"] = physical
        await db.products.update_one({"id": body.item_id}, {"$set": {"variants": variants, "updated_at": now_iso()}})
        target = body.variant_sku
    else:
        raise HTTPException(400, "Invalid inventory kind")
    delta = physical - before
    await record_movement(body.kind, target, "opname", delta, "opname", before, physical, user["id"], body.notes)
    await audit(user, "opname", body.kind, target, {"stock": before}, {"stock": physical, "delta": delta, "notes": body.notes})
    return {"ok": True, "before": before, "after": physical, "delta": delta}

@api.post("/inventory/products/adjust")
async def adjust_variant(body: VariantAdjustIn, user: dict = Depends(require_module("inventory"))):
    p = await db.products.find_one({"id": body.product_id})
    if not p: raise HTTPException(404, "Product not found")
    variants = p.get("variants", [])
    for v in variants:
        if v["sku"] == body.variant_sku:
            before = float(v.get("stock", 0))
            if not math.isfinite(body.quantity) or before + body.quantity < 0:
                raise HTTPException(400, "Stock cannot be negative")
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

@api.put("/purchase_orders/{po_id}")
@transactional
async def update_po(po_id: str, body: Dict[str, Any], user: dict = Depends(require_module("purchasing"))):
    po = await db.purchase_orders.find_one({"id": po_id})
    if not po:
        raise HTTPException(404, "PO not found")
    if po.get("received_status") == "received" or po.get("payment_status") == "paid":
        raise HTTPException(400, "Only pending and unpaid purchase orders can be edited")
    items = body.get("items", [])
    if not items:
        raise HTTPException(400, "At least one purchase item is required")
    subtotal = 0.0
    for item in items:
        quantity = positive(item.get("quantity", 0), "Purchase quantity")
        unit_cost = nonnegative(item.get("unit_cost", 0), "Unit cost")
        subtotal += quantity * unit_cost
    updated = {
        "supplier_id": body.get("supplier_id", po.get("supplier_id")),
        "account_id": body.get("account_id", po.get("account_id")),
        "date": body.get("date", po.get("date")),
        "items": items,
        "discount": nonnegative(body.get("discount", 0), "Discount"),
        "shipping": nonnegative(body.get("shipping", 0), "Shipping"),
        "tax": nonnegative(body.get("tax", 0), "Tax"),
        "subtotal": subtotal,
        "total": subtotal - nonnegative(body.get("discount", 0), "Discount") + nonnegative(body.get("shipping", 0), "Shipping") + nonnegative(body.get("tax", 0), "Tax"),
        "updated_at": now_iso(),
    }
    await db.purchase_orders.update_one({"id": po_id}, {"$set": updated})
    await audit(user, "update", "purchase_order", po_id, po, {**po, **updated})
    return {**po, **updated}

@api.post("/purchase_orders/{po_id}/receive")
@transactional
async def receive_po(po_id: str, user: dict = Depends(require_module("purchasing"))):
    po = await db.purchase_orders.find_one({"id": po_id})
    if not po: raise HTTPException(404, "PO not found")
    if po.get("received_status") == "received":
        raise HTTPException(400, "Already received")
    for item in po.get("items", []):
        mid = item.get("material_id")
        qty = positive(item.get("quantity", 0), "Purchase quantity")
        if not mid:
            raise HTTPException(400, "Purchase order item is missing material")
        if not await db.materials.find_one({"id": mid}):
            raise HTTPException(400, f"Material {mid} not found")
    for item in po.get("items", []):
        mid = item.get("material_id")
        qty = positive(item.get("quantity", 0), "Purchase quantity")
        m = await db.materials.find_one({"id": mid})
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


@api.post("/purchase_orders/{po_id}/pay")
@transactional
async def pay_purchase_order(po_id: str, body: Dict[str, Any], user: dict = Depends(require_module("finance"))):
    po = await db.purchase_orders.find_one({"id": po_id})
    if not po:
        raise HTTPException(404, "PO not found")
    if po.get("payment_status") == "paid":
        raise HTTPException(400, "Purchase order already paid")
    if po.get("received_status") != "received":
        raise HTTPException(400, "Receive the purchase order before paying it")
    await create_financial_transaction(user, "expense", float(po.get("total", 0)), body.get("account_id"), f"Pelunasan {po['po_number']}", "purchase_order", po_id)
    await db.purchase_orders.update_one({"id": po_id}, {"$set": {"payment_status": "paid", "paid_at": now_iso(), "payment_account_id": body.get("account_id"), "updated_at": now_iso()}})
    return {"ok": True, "payment_status": "paid"}

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
@transactional
async def complete_production(pid: str, body: Dict[str, Any], user: dict = Depends(require_module("production"))):
    po = await db.production_orders.find_one({"id": pid})
    if not po: raise HTTPException(404, "Not found")
    if po.get("status") == "completed":
        raise HTTPException(400, "Already completed")
    planned_qty = positive(po.get("quantity", 0), "quantity")
    qty_passed = nonnegative(body.get("quantity_passed", planned_qty), "quantity_passed")
    qty_rejected = nonnegative(body.get("quantity_rejected", 0), "quantity_rejected")
    if not math.isclose(qty_passed + qty_rejected, planned_qty, rel_tol=0, abs_tol=1e-9):
        raise HTTPException(400, "Passed and rejected quantity must equal planned quantity")
    variant_sku = body.get("variant_sku") or po.get("variant_sku")
    product_id = po.get("product_id")
    bom_items = po.get("bom_items", [])
    if not bom_items:
        raise HTTPException(400, "Production order has no BOM items")
    material_requirements = {}
    for bi in bom_items:
        mid = bi.get("material_id")
        if not mid:
            raise HTTPException(400, "BOM item is missing material")
        per_unit = positive(bi.get("quantity", 0), "BOM quantity")
        material_requirements[mid] = material_requirements.get(mid, 0) + per_unit * (qty_passed + qty_rejected)
    for mid, needed in material_requirements.items():
        material = await db.materials.find_one({"id": mid})
        if not material:
            raise HTTPException(400, f"Material {mid} not found")
        if float(material.get("stock", 0)) < needed:
            raise HTTPException(400, f"Insufficient material stock for {mid}")
    if not product_id or not variant_sku:
        raise HTTPException(400, "Production output product and variant are required")
    product = await db.products.find_one({"id": product_id})
    if not product or not any(v.get("sku") == variant_sku for v in product.get("variants", [])):
        raise HTTPException(400, "Production output variant not found")
    total_material_cost = 0.0
    # consume materials
    for bi in bom_items:
        mid = bi["material_id"]; per_unit = positive(bi.get("quantity", 0), "BOM quantity")
        needed = per_unit * (qty_passed + qty_rejected)
        m = await db.materials.find_one({"id": mid})
        if not m: raise HTTPException(400, f"Material {mid} not found")
        before = float(m.get("stock", 0))
        after = before - needed
        total_material_cost += needed * float(m.get("cost", 0))
        await db.materials.update_one({"id": mid}, {"$set": {"stock": after, "updated_at": now_iso()}})
        await record_movement("material", mid, pid, -needed, "production", before, after, user["id"], f"Prod {po['prod_number']}")
    # add finished goods
    p = product
    variants = p.get("variants", [])
    unit_cost = (total_material_cost / (qty_passed + qty_rejected)) if (qty_passed + qty_rejected) > 0 else 0
    for v in variants:
        if v["sku"] == variant_sku:
            before = float(v.get("stock", 0))
            v["stock"] = before + qty_passed
            after = v["stock"]
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
async def calculate_marketplace_fee(channel: str, fee_base: float, explicit_fee: Any = None) -> float:
    if explicit_fee is not None:
        return nonnegative(explicit_fee, "Marketplace fee")
    marketplace = await db.marketplaces.find_one({"name": channel})
    if not marketplace:
        return 0
    fee_pct = sum(float(marketplace.get(field, 0)) for field in ("admin_fee_pct", "service_fee_pct", "payment_fee_pct"))
    commission = fee_base * fee_pct / 100
    cap = nonnegative(marketplace.get("commission_cap", 0), "Commission cap")
    if cap > 0:
        commission = min(commission, cap)
    return commission


def is_marketplace_channel(channel: str) -> bool:
    return channel in {"Shopee", "TikTok Shop"}


async def get_marketplace_fixed_fees(channel: str) -> dict:
    marketplace = await db.marketplaces.find_one({"name": channel}) or {}
    return {
        "handling_fee": nonnegative(marketplace.get("handling_fee", 0), "Handling fee"),
        "logistics_fee": nonnegative(marketplace.get("logistics_fee", 0), "Logistics fee"),
        "return_fee_cap": nonnegative(marketplace.get("return_fee_cap", 0), "Return fee cap"),
    }

@api.get("/sales_orders", dependencies=[Depends(require_module("sales"))])
async def list_sales():
    return await db.sales_orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)

@api.get("/sales_orders/{sid}/pdf")
async def sales_order_pdf(sid: str, user: dict = Depends(require_module("sales"))):
    sales_order = await db.sales_orders.find_one({"id": sid}, {"_id": 0})
    if not sales_order:
        raise HTTPException(404, "Order not found")
    profile = await db.settings_kv.find_one({"id": "business_profile"}, {"_id": 0}) or {}

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError as exc:
        raise HTTPException(503, "PDF dependency is not installed") from exc

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SmallMuted", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#64748b")))
    styles.add(ParagraphStyle(name="InvoiceTitle", parent=styles["Heading1"], fontSize=20, leading=24, spaceAfter=4))
    styles.add(ParagraphStyle(name="Right", parent=styles["Normal"], alignment=2))

    business_name = profile.get("business_name") or profile.get("name") or "NexaBiz Business"
    business_address = profile.get("address") or profile.get("business_address") or ""
    business_phone = profile.get("phone") or ""
    business_email = profile.get("email") or ""
    tax_name = profile.get("tax_name") or "Tax"
    currency = profile.get("currency") or "IDR"
    locale = profile.get("locale") or "en-US"

    def money(value):
        try:
            return f"{currency} {float(value or 0):,.0f}"
        except (TypeError, ValueError):
            return f"{currency} 0"

    def safe(value):
        return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    customer = safe(sales_order.get("customer_name") or "Guest")
    order_number = safe(sales_order.get("order_number") or sid)
    date_value = safe(str(sales_order.get("date") or "")[:10])
    story = [
        [Paragraph(f"<b>{safe(business_name)}</b><br/>{safe(business_address)}<br/>{safe(business_phone)} {safe(business_email)}", styles["Normal"]),
         Paragraph("<b>SALES INVOICE</b>", styles["Right"])],
        [Paragraph(f"<font size='8'>Customer: {customer}<br/>Invoice: {order_number}<br/>Date: {date_value}</font>", styles["SmallMuted"]), ""],
        [Spacer(1, 6)],
    ]
    header = [Paragraph("<b>Item</b>", styles["Normal"]), Paragraph("<b>Qty</b>", styles["Right"]), Paragraph("<b>Unit price</b>", styles["Right"]), Paragraph("<b>Amount</b>", styles["Right"])]
    rows = [header]
    for item in sales_order.get("items") or []:
        quantity = float(item.get("quantity") or 0)
        unit_price = float(item.get("selling_price") or 0)
        rows.append([
            Paragraph(safe(item.get("product_name") or item.get("variant_sku") or "Item"), styles["Normal"]),
            Paragraph(f"{quantity:g}", styles["Right"]),
            Paragraph(money(unit_price), styles["Right"]),
            Paragraph(money(quantity * unit_price), styles["Right"]),
        ])
    table = Table(rows, colWidths=[85 * mm, 18 * mm, 38 * mm, 38 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([table, Spacer(1, 10)])
    summary = [
        ["Subtotal", money(sales_order.get("subtotal"))],
        ["Discount", f"- {money(sales_order.get('discount'))}"],
        ["Shipping", money(sales_order.get("shipping"))],
        [tax_name, money(sales_order.get("tax"))],
        ["Total", money(sales_order.get("total"))],
        ["Payment", safe(sales_order.get("payment_method") or sales_order.get("payment_status") or "-")],
    ]
    summary_table = Table([[Paragraph(f"<b>{safe(label)}</b>" if label == "Total" else safe(label), styles["Normal"]),
                            Paragraph(f"<b>{value}</b>" if label == "Total" else value, styles["Right"])] for label, value in summary], colWidths=[141 * mm, 38 * mm])
    summary_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, 4), (-1, 4), 0.8, colors.HexColor("#0f172a")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([summary_table, Spacer(1, 14), Paragraph("Thank you for your business.", styles["SmallMuted"])])
    document.build(story)
    buffer.seek(0)
    filename = f"invoice-{sales_order.get('order_number') or sid}.pdf"
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

@api.post("/sales_orders")
@transactional
async def create_sales(body: Dict[str, Any], user: dict = Depends(require_module("sales"))):
    body["id"] = body.get("id") or new_id()
    body["order_number"] = body.get("order_number") or f"SO-{datetime.now().strftime('%y%m%d')}-{body['id'][:4].upper()}"
    existing = await db.sales_orders.find_one({"order_number": body["order_number"]})
    if existing:
        raise HTTPException(409, "Order number already exists")
    items = body.get("items", [])
    subtotal = 0.0; cogs = 0.0
    if not items:
        raise HTTPException(400, "At least one sales item is required")
    stock_by_variant = {}
    product_by_id = {}
    for it in items:
        pid = it.get("product_id")
        vsku = it.get("variant_sku")
        qty = positive(it.get("quantity", 0), "Item quantity")
        nonnegative(it.get("selling_price", 0), "Selling price")
        p = await db.products.find_one({"id": pid})
        if not p:
            raise HTTPException(400, f"Product {pid} not found")
        variant = next((v for v in p.get("variants", []) if v.get("sku") == vsku), None)
        if not variant:
            raise HTTPException(400, f"Variant {vsku} not found")
        key = (pid, vsku)
        stock_by_variant[key] = stock_by_variant.get(key, 0) + qty
        product_by_id[pid] = p
    for (pid, vsku), requested in stock_by_variant.items():
        p = product_by_id[pid]
        variant = next(v for v in p.get("variants", []) if v.get("sku") == vsku)
        if float(variant.get("stock", 0)) < requested:
            raise HTTPException(400, f"Insufficient stock for {vsku}")
    # deduct inventory
    for it in items:
        pid = it["product_id"]; vsku = it["variant_sku"]; qty = positive(it["quantity"], "Item quantity")
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
    sales_channel = body.get("sales_channel", "Direct")
    fee_base = max(0, subtotal - discount - voucher)
    marketplace_fee = await calculate_marketplace_fee(sales_channel, fee_base, body.get("marketplace_fee"))
    live_video_fee_pct = nonnegative(body.get("live_video_fee_pct", 0), "Live/Video fee")
    affiliate_fee_pct = nonnegative(body.get("affiliate_fee_pct", 0), "Affiliate fee")
    live_video_fee = fee_base * live_video_fee_pct / 100
    affiliate_fee = fee_base * affiliate_fee_pct / 100
    marketplace_fixed_fees = await get_marketplace_fixed_fees(sales_channel)
    return_rate_pct = nonnegative(body.get("return_rate_pct", 0), "Return rate")
    if return_rate_pct > 100:
        raise HTTPException(400, "Return rate cannot exceed 100%")
    return_allowance = marketplace_fixed_fees["return_fee_cap"] * return_rate_pct / 100
    handling_fee = marketplace_fixed_fees["handling_fee"]
    logistics_fee = marketplace_fixed_fees["logistics_fee"]
    other_fee = nonnegative(body.get("other_fee", 0), "Other fee") + live_video_fee + affiliate_fee + handling_fee + logistics_fee + return_allowance
    advertising = float(body.get("advertising_cost", 0))
    total = subtotal - discount - voucher + shipping
    net = total - marketplace_fee - other_fee - advertising - cogs
    body.update({
        "subtotal": subtotal, "cogs": cogs, "discount": discount, "voucher": voucher,
        "shipping": shipping, "marketplace_fee": marketplace_fee, "other_fee": other_fee,
        "marketplace_fee_base": fee_base, "live_video_fee_pct": live_video_fee_pct,
        "live_video_fee": live_video_fee, "affiliate_fee_pct": affiliate_fee_pct,
        "affiliate_fee": affiliate_fee,
        "handling_fee": handling_fee, "logistics_fee": logistics_fee,
        "return_rate_pct": return_rate_pct, "return_allowance": return_allowance,
        "advertising_cost": advertising, "total": total, "net_profit": net,
        "payment_status": body.get("payment_status", "paid"),
        "fulfillment_status": body.get("fulfillment_status", "processing"),
        "sales_channel": sales_channel,
        "date": body.get("date") or now_iso(),
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    await db.sales_orders.insert_one(body)
    # financial txn if paid
    if body["payment_status"] == "paid" and not is_marketplace_channel(sales_channel):
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
    if ttype not in {"income", "expense", "transfer", "owner_investment", "owner_withdrawal"}:
        raise HTTPException(400, "Invalid transaction type")
    amount = positive(amount, "Transaction amount")
    account_id = account_id or await get_default_account_id()
    if not account_id:
        raise HTTPException(400, "A financial account is required")
    if not await db.accounts.find_one({"id": account_id}):
        raise HTTPException(400, "Financial account not found")
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

async def create_document_journal(user, document_type, document):
    """Post the accrual entry for an invoice or vendor bill once."""
    if await db.journal_entries.find_one({"source_type": document_type, "source_id": document["id"]}):
        return
    amount = positive(document.get("amount", 0), "Document amount")
    cash_kind = "receivable" if document_type == "invoices" else "expense"
    offset_kind = "revenue" if document_type == "invoices" else "payable"
    debit_account = await db.accounts.find_one({"kind": cash_kind})
    credit_account = await db.accounts.find_one({"kind": offset_kind})
    if document_type == "bills" and not credit_account:
        credit_account = await db.accounts.find_one({"kind": "liability"})
    if not debit_account or not credit_account:
        # Existing installations may not have the optional chart accounts yet.
        return
    lines = [
        {"account_id": debit_account["id"], "description": document.get("party_name", ""), "debit": amount if document_type == "invoices" else 0, "credit": amount if document_type == "bills" else 0},
        {"account_id": credit_account["id"], "description": document.get("description", ""), "debit": amount if document_type == "bills" else 0, "credit": amount if document_type == "invoices" else 0},
    ]
    await db.journal_entries.insert_one({
        "id": new_id(), "date": document.get("date") or now_iso(),
        "reference": document.get("number", document["id"]),
        "description": f"{'Invoice' if document_type == 'invoices' else 'Bill'} {document.get('number', document['id'])}",
        "lines": lines, "total": amount, "source_type": document_type,
        "source_id": document["id"], "created_by": user["id"], "created_at": now_iso(),
    })

async def create_payment_journal(user, document_type, document_id, amount, account_id):
    account = await db.accounts.find_one({"id": account_id})
    counter_kind = "receivable" if document_type == "invoice" else "liability"
    counter = await db.accounts.find_one({"kind": counter_kind})
    if not account or not counter:
        return
    await db.journal_entries.insert_one({
        "id": new_id(), "date": now_iso(),
        "reference": f"{'INV' if document_type == 'invoice' else 'BILL'}-PAY-{document_id[:8]}",
        "description": f"{'Invoice' if document_type == 'invoice' else 'Bill'} payment",
        "lines": [
            {"account_id": account_id, "description": "Payment account", "debit": amount if document_type == "invoice" else 0, "credit": amount if document_type == "bill" else 0},
            {"account_id": counter["id"], "description": "Settlement", "debit": amount if document_type == "bill" else 0, "credit": amount if document_type == "invoice" else 0},
        ],
        "total": amount, "source_type": f"{document_type}_payment",
        "source_id": document_id, "created_by": user["id"], "created_at": now_iso(),
    })

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
@transactional
async def create_txn(body: FinTxnIn, user: dict = Depends(require_module("finance"))):
    await create_financial_transaction(user, body.type, body.amount, body.account_id, body.description, "manual", "")
    return {"ok": True}

# ---------- FINANCE SUITE ----------
class JournalLine(BaseModel):
    account_id: str
    description: str = ""
    debit: float = 0
    credit: float = 0

class JournalEntryIn(BaseModel):
    date: Optional[str] = None
    reference: str = ""
    description: str
    lines: List[JournalLine]

@api.get("/finance/journal_entries")
async def list_journal_entries(user: dict = Depends(require_module("finance"))):
    return await db.journal_entries.find({}, {"_id": 0}).sort("date", -1).to_list(1000)

@api.post("/finance/journal_entries")
@transactional
async def create_journal_entry(body: JournalEntryIn, user: dict = Depends(require_module("finance"))):
    if len(body.lines) < 2:
        raise HTTPException(400, "A journal entry needs at least two lines")
    debit = sum(nonnegative(line.debit, "Debit") for line in body.lines)
    credit = sum(nonnegative(line.credit, "Credit") for line in body.lines)
    if abs(debit - credit) > 0.005:
        raise HTTPException(400, "Debits and credits must balance")
    if any((line.debit > 0 and line.credit > 0) or (line.debit == 0 and line.credit == 0) for line in body.lines):
        raise HTTPException(400, "Each journal line must have either debit or credit")
    for line in body.lines:
        if not await db.accounts.find_one({"id": line.account_id}):
            raise HTTPException(400, f"Account {line.account_id} not found")
    entry = {"id": new_id(), "date": body.date or now_iso(), "reference": body.reference,
             "description": body.description, "lines": [line.model_dump() for line in body.lines],
             "total": debit, "created_by": user["id"], "created_at": now_iso()}
    await db.journal_entries.insert_one(entry)
    await audit(user, "create", "journal_entry", entry["id"], None, entry)
    entry.pop("_id", None)
    return entry

@api.get("/finance/ap-ar")
async def list_ap_ar(user: dict = Depends(require_module("finance"))):
    invoices = await db.invoices.find({}, {"_id": 0}).sort("due_date", 1).to_list(1000)
    bills = await db.bills.find({}, {"_id": 0}).sort("due_date", 1).to_list(1000)
    return {"receivables": invoices, "payables": bills,
            "receivables_total": sum(float(x.get("amount", 0)) - float(x.get("paid_amount", 0)) for x in invoices if x.get("status") != "cancelled"),
            "payables_total": sum(float(x.get("amount", 0)) - float(x.get("paid_amount", 0)) for x in bills if x.get("status") != "cancelled")}

@api.post("/finance/invoices/{item_id}/payment")
@transactional
async def pay_invoice(item_id: str, body: Dict[str, Any], user: dict = Depends(require_module("finance"))):
    invoice = await db.invoices.find_one({"id": item_id})
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    amount = positive(body.get("amount", 0), "Payment amount")
    outstanding = float(invoice.get("amount", 0)) - float(invoice.get("paid_amount", 0))
    if amount > outstanding:
        raise HTTPException(400, "Payment exceeds outstanding amount")
    paid = float(invoice.get("paid_amount", 0)) + amount
    status_value = "paid" if paid >= float(invoice.get("amount", 0)) else "partial"
    await db.invoices.update_one({"id": item_id}, {"$set": {"paid_amount": paid, "status": status_value, "updated_at": now_iso()}})
    account_id = body.get("account_id") or await get_default_account_id()
    await create_financial_transaction(user, "income", amount, account_id, f"Invoice {invoice.get('number', item_id)}", "invoice_payment", item_id)
    await create_payment_journal(user, "invoice", item_id, amount, account_id)
    return {"ok": True, "paid_amount": paid, "status": status_value}

@api.post("/finance/bills/{item_id}/payment")
@transactional
async def pay_bill(item_id: str, body: Dict[str, Any], user: dict = Depends(require_module("finance"))):
    bill = await db.bills.find_one({"id": item_id})
    if not bill:
        raise HTTPException(404, "Bill not found")
    amount = positive(body.get("amount", 0), "Payment amount")
    outstanding = float(bill.get("amount", 0)) - float(bill.get("paid_amount", 0))
    if amount > outstanding:
        raise HTTPException(400, "Payment exceeds outstanding amount")
    paid = float(bill.get("paid_amount", 0)) + amount
    status_value = "paid" if paid >= float(bill.get("amount", 0)) else "partial"
    await db.bills.update_one({"id": item_id}, {"$set": {"paid_amount": paid, "status": status_value, "updated_at": now_iso()}})
    account_id = body.get("account_id") or await get_default_account_id()
    await create_financial_transaction(user, "expense", amount, account_id, f"Bill {bill.get('number', item_id)}", "bill_payment", item_id)
    await create_payment_journal(user, "bill", item_id, amount, account_id)
    return {"ok": True, "paid_amount": paid, "status": status_value}

@api.get("/finance/tax-summary")
async def tax_summary(start: str = "", end: str = "", user: dict = Depends(require_module("finance"))):
    query = {}
    if start: query["date"] = {"$gte": start}
    if end: query.setdefault("date", {})["$lte"] = end
    sales = await db.sales_orders.find(query, {"_id": 0}).to_list(10000)
    purchases = await db.purchase_orders.find(query, {"_id": 0}).to_list(10000)
    output = sum(float(x.get("tax", 0)) for x in sales)
    input_tax = sum(float(x.get("tax", 0)) for x in purchases)
    return {"output_tax": output, "input_tax": input_tax, "net_tax": output - input_tax, "period_start": start, "period_end": end}

# ---------- STANDARD COA & OPENING BALANCE ----------
STANDARD_COA = [
    # 1-xxxx ASET (ASSETS)
    {"code": "1-10001", "name": "Kas Tunai", "kind": "cash", "account_type": "asset", "subtype": "Kas & Bank", "normal_balance": "debit", "is_default": True, "is_system": True},
    {"code": "1-10002", "name": "Bank BCA", "kind": "bank", "account_type": "asset", "subtype": "Kas & Bank", "normal_balance": "debit", "is_system": False},
    {"code": "1-10003", "name": "Blu by BCA Digital", "kind": "bank", "account_type": "asset", "subtype": "Kas & Bank", "normal_balance": "debit", "is_system": False},
    {"code": "1-10004", "name": "SeaBank", "kind": "bank", "account_type": "asset", "subtype": "Kas & Bank", "normal_balance": "debit", "is_system": False},
    {"code": "1-10005", "name": "BRI", "kind": "bank", "account_type": "asset", "subtype": "Kas & Bank", "normal_balance": "debit", "is_system": False},
    {"code": "1-10010", "name": "E-Wallet DANA", "kind": "wallet", "account_type": "asset", "subtype": "Kas & Bank", "normal_balance": "debit", "is_system": False},
    {"code": "1-10011", "name": "GoPay", "kind": "wallet", "account_type": "asset", "subtype": "Kas & Bank", "normal_balance": "debit", "is_system": False},
    {"code": "1-10020", "name": "Shopee Balance", "kind": "marketplace", "account_type": "asset", "subtype": "Kas & Bank", "normal_balance": "debit", "is_system": False},
    {"code": "1-10021", "name": "TikTok Shop Balance", "kind": "marketplace", "account_type": "asset", "subtype": "Kas & Bank", "normal_balance": "debit", "is_system": False},
    {"code": "1-10100", "name": "Piutang Usaha", "kind": "receivable", "account_type": "asset", "subtype": "Piutang", "normal_balance": "debit", "is_system": True},
    {"code": "1-10200", "name": "Persediaan Barang Jadi", "kind": "inventory", "account_type": "asset", "subtype": "Persediaan", "normal_balance": "debit", "is_system": True},
    {"code": "1-10210", "name": "Persediaan Bahan Baku", "kind": "inventory", "account_type": "asset", "subtype": "Persediaan", "normal_balance": "debit", "is_system": True},
    {"code": "1-10800", "name": "Aset Tetap & Peralatan", "kind": "asset", "account_type": "asset", "subtype": "Aset Tetap", "normal_balance": "debit", "is_system": False},
    {"code": "1-10890", "name": "Akumulasi Penyusutan Aset", "kind": "contra_asset", "account_type": "asset", "subtype": "Aset Tetap", "normal_balance": "credit", "is_system": False},
    
    # 2-xxxx KEWAJIBAN (LIABILITIES)
    {"code": "2-10100", "name": "Hutang", "kind": "liability", "account_type": "liability", "subtype": "Kewajiban Lancar", "normal_balance": "credit", "is_system": True},
    {"code": "2-10200", "name": "Hutang Gaji & Komisi", "kind": "liability", "account_type": "liability", "subtype": "Kewajiban Lancar", "normal_balance": "credit", "is_system": False},
    {"code": "2-10300", "name": "Hutang Pajak", "kind": "liability", "account_type": "liability", "subtype": "Kewajiban Lancar", "normal_balance": "credit", "is_system": False},
    {"code": "2-20100", "name": "Hutang Bank / Jangka Panjang", "kind": "liability", "account_type": "liability", "subtype": "Kewajiban Jangka Panjang", "normal_balance": "credit", "is_system": False},
    
    # 3-xxxx EKUITAS (EQUITY)
    {"code": "3-10000", "name": "Modal Pemilik / Disetor", "kind": "equity", "account_type": "equity", "subtype": "Ekuitas", "normal_balance": "credit", "is_system": True},
    {"code": "3-10001", "name": "Ekuitas Saldo Awal", "kind": "equity", "account_type": "equity", "subtype": "Ekuitas", "normal_balance": "credit", "is_system": True},
    {"code": "3-10900", "name": "Laba Ditahan", "kind": "equity", "account_type": "equity", "subtype": "Ekuitas", "normal_balance": "credit", "is_system": True},
    
    # 4-xxxx PENDAPATAN (REVENUE)
    {"code": "4-10000", "name": "Pendapatan Penjualan", "kind": "revenue", "account_type": "revenue", "subtype": "Pendapatan Operasional", "normal_balance": "credit", "is_system": True},
    {"code": "4-10100", "name": "Pendapatan Custom / Jasa", "kind": "revenue", "account_type": "revenue", "subtype": "Pendapatan Operasional", "normal_balance": "credit", "is_system": False},
    {"code": "4-10900", "name": "Pendapatan Lain-lain", "kind": "revenue", "account_type": "revenue", "subtype": "Pendapatan Non-Operasional", "normal_balance": "credit", "is_system": False},
    
    # 5-xxxx BEBAN POKOK PENJUALAN (COGS)
    {"code": "5-10000", "name": "Beban Pokok Penjualan (HPP)", "kind": "cogs", "account_type": "cogs", "subtype": "Beban Pokok Penjualan", "normal_balance": "debit", "is_system": True},
    
    # 6-xxxx BEBAN OPERASIONAL (EXPENSES)
    {"code": "6-10001", "name": "Beban Iklan & Marketing", "kind": "expense", "account_type": "expense", "subtype": "Beban Operasional", "normal_balance": "debit", "is_system": False},
    {"code": "6-10002", "name": "Beban Listrik, Air & Internet", "kind": "expense", "account_type": "expense", "subtype": "Beban Operasional", "normal_balance": "debit", "is_system": False},
    {"code": "6-10003", "name": "Beban Packaging & Ekspedisi", "kind": "expense", "account_type": "expense", "subtype": "Beban Operasional", "normal_balance": "debit", "is_system": False},
    {"code": "6-10004", "name": "Beban Biaya Admin Marketplace", "kind": "expense", "account_type": "expense", "subtype": "Beban Operasional", "normal_balance": "debit", "is_system": False},
    {"code": "6-10005", "name": "Beban Gaji & Upah Staf", "kind": "expense", "account_type": "expense", "subtype": "Beban Operasional", "normal_balance": "debit", "is_system": False},
    {"code": "6-10006", "name": "Beban Sewa Tempat", "kind": "expense", "account_type": "expense", "subtype": "Beban Operasional", "normal_balance": "debit", "is_system": False},
    {"code": "6-10007", "name": "Beban Penyusutan Aset", "kind": "expense", "account_type": "expense", "subtype": "Beban Operasional", "normal_balance": "debit", "is_system": False},
    {"code": "6-10099", "name": "Beban Operasional Lainnya", "kind": "expense", "account_type": "expense", "subtype": "Beban Operasional", "normal_balance": "debit", "is_system": False},
]

async def ensure_coa_seeded():
    for item in STANDARD_COA:
        query = {"$or": [{"code": item["code"]}, {"name": item["name"]}]}
        existing = await db.accounts.find_one(query)
        if not existing:
            doc = {
                "id": new_id(),
                "balance": 0,
                "status": "active",
                "created_at": now_iso(),
                "updated_at": now_iso(),
                **item,
            }
            await db.accounts.insert_one(doc)
        else:
            updates = {}
            for field in ["code", "account_type", "subtype", "normal_balance", "is_system", "kind"]:
                if field in item and (field not in existing or not existing[field]):
                    updates[field] = item[field]
            if updates:
                updates["updated_at"] = now_iso()
                await db.accounts.update_one({"id": existing["id"]}, {"$set": updates})

class OpeningBalanceLine(BaseModel):
    account_id: str
    debit: float = 0
    credit: float = 0

class OpeningBalanceIn(BaseModel):
    as_of_date: str = "2026-01-01"
    lines: List[OpeningBalanceLine]
    auto_balance: bool = True

@api.get("/finance/opening-balance", dependencies=[Depends(require_module("finance"))])
async def get_opening_balance():
    meta = await db.settings_kv.find_one({"id": "opening_balance_meta"}, {"_id": 0}) or {}
    as_of_date = meta.get("as_of_date", "2026-01-01")
    accounts = await db.accounts.find({"status": {"$ne": "archived"}}, {"_id": 0}).sort("code", 1).to_list(1000)
    
    opening_journal = await db.journal_entries.find_one({"source_type": "opening_balance"}, {"_id": 0})
    lines_by_acc = {}
    if opening_journal:
        for l in opening_journal.get("lines", []):
            lines_by_acc[l["account_id"]] = l
            
    total_debit = 0.0
    total_credit = 0.0
    result_accounts = []
    for acc in accounts:
        line = lines_by_acc.get(acc["id"], {})
        d = float(line.get("debit", acc.get("opening_debit", 0)))
        c = float(line.get("credit", acc.get("opening_credit", 0)))
        total_debit += d
        total_credit += c
        result_accounts.append({
            "id": acc["id"],
            "code": acc.get("code", "-"),
            "name": acc.get("name", ""),
            "account_type": acc.get("account_type", "asset"),
            "subtype": acc.get("subtype", "Kas & Bank"),
            "normal_balance": acc.get("normal_balance", "debit"),
            "is_system": acc.get("is_system", False),
            "opening_debit": d,
            "opening_credit": c,
        })
    diff = round(total_debit - total_credit, 2)
    return {
        "as_of_date": as_of_date,
        "is_set": bool(opening_journal),
        "total_debit": total_debit,
        "total_credit": total_credit,
        "difference": diff,
        "is_balanced": abs(diff) < 0.005,
        "accounts": result_accounts,
    }

@api.post("/finance/opening-balance", dependencies=[Depends(require_module("finance"))])
@transactional
async def save_opening_balance(body: OpeningBalanceIn, user: dict = Depends(require_module("finance"))):
    as_of_date = body.as_of_date or "2026-01-01"
    raw_lines = [l.model_dump() for l in body.lines if (l.debit > 0 or l.credit > 0)]
    
    total_debit = sum(float(l["debit"]) for l in raw_lines)
    total_credit = sum(float(l["credit"]) for l in raw_lines)
    diff = round(total_debit - total_credit, 2)
    
    lines = list(raw_lines)
    if abs(diff) > 0.005:
        if body.auto_balance:
            eq_acc = await db.accounts.find_one({"$or": [{"code": "3-10001"}, {"name": "Ekuitas Saldo Awal"}]})
            if not eq_acc:
                eq_id = new_id()
                eq_acc = {
                    "id": eq_id, "code": "3-10001", "name": "Ekuitas Saldo Awal",
                    "account_type": "equity", "subtype": "Ekuitas", "normal_balance": "credit",
                    "is_system": True, "balance": 0, "status": "active", "created_at": now_iso()
                }
                await db.accounts.insert_one(eq_acc)
            
            existing_line_idx = next((i for i, l in enumerate(lines) if l["account_id"] == eq_acc["id"]), None)
            if diff > 0:
                if existing_line_idx is not None:
                    lines[existing_line_idx]["credit"] = float(lines[existing_line_idx]["credit"]) + diff
                else:
                    lines.append({"account_id": eq_acc["id"], "debit": 0, "credit": diff, "description": "Penyeimbang Saldo Awal"})
            else:
                if existing_line_idx is not None:
                    lines[existing_line_idx]["debit"] = float(lines[existing_line_idx]["debit"]) + abs(diff)
                else:
                    lines.append({"account_id": eq_acc["id"], "debit": abs(diff), "credit": 0, "description": "Penyeimbang Saldo Awal"})
            
            total_debit = sum(float(l["debit"]) for l in lines)
            total_credit = sum(float(l["credit"]) for l in lines)
        else:
            raise HTTPException(400, f"Total Debit ({total_debit}) dan Credit ({total_credit}) belum seimbang. Selisih: {diff}")
            
    await db.journal_entries.delete_many({"source_type": "opening_balance"})
    
    if lines:
        entry = {
            "id": new_id(),
            "date": f"{as_of_date}T00:00:00Z" if len(as_of_date) == 10 else as_of_date,
            "reference": "OPENING-BAL",
            "description": "Saldo Awal Pembukuan",
            "lines": lines,
            "total": total_debit,
            "source_type": "opening_balance",
            "source_id": "opening_balance",
            "created_by": user["id"],
            "created_at": now_iso(),
        }
        await db.journal_entries.insert_one(entry)
        
    for l in lines:
        acc_id = l["account_id"]
        acc = await db.accounts.find_one({"id": acc_id})
        if acc:
            normal = acc.get("normal_balance", "debit")
            net_change = (l["debit"] - l["credit"]) if normal == "debit" else (l["credit"] - l["debit"])
            await db.accounts.update_one(
                {"id": acc_id},
                {"$set": {
                    "opening_debit": l["debit"],
                    "opening_credit": l["credit"],
                    "balance": max(0, net_change),
                    "updated_at": now_iso()
                }}
            )
            
    await db.settings_kv.update_one(
        {"id": "opening_balance_meta"},
        {"$set": {"id": "opening_balance_meta", "as_of_date": as_of_date, "updated_at": now_iso()}},
        upsert=True
    )
    await audit(user, "update", "opening_balance", "opening_balance", None, {"as_of_date": as_of_date, "total": total_debit})
    return {"ok": True, "as_of_date": as_of_date, "total": total_debit, "is_balanced": True}

@api.get("/crm/summary")
async def crm_summary(user: dict = Depends(require_module("crm"))):
    customers = await db.customers.find({"status": {"$ne": "archived"}}, {"_id": 0}).to_list(1000)
    activities = await db.crm_activities.find({}, {"_id": 0}).sort("due_date", 1).to_list(1000)
    return {"customers": customers, "activities": activities,
            "total_customers": len(customers), "open_followups": len([x for x in activities if x.get("status") != "completed"])}

@api.get("/dashboard/cashflow")
async def dashboard_cashflow(user: dict = Depends(require_module("dashboard"))):
    today = datetime.now(timezone.utc).date().isoformat()
    transactions = await db.financial_transactions.find({"date": {"$gte": today}}, {"_id": 0}).to_list(5000)
    cash_in = sum(float(x.get("amount", 0)) for x in transactions if x.get("type") in {"income", "owner_investment"})
    cash_out = sum(float(x.get("amount", 0)) for x in transactions if x.get("type") in {"expense", "owner_withdrawal"})
    accounts = await db.accounts.find({}, {"_id": 0, "name": 1, "balance": 1, "kind": 1}).to_list(100)
    return {"date": today, "cash_in": cash_in, "cash_out": cash_out, "net": cash_in - cash_out,
            "balance": sum(float(x.get("balance", 0)) for x in accounts), "accounts": accounts}

# ---------- EXPENSES ----------
@api.get("/expenses", dependencies=[Depends(require_module("finance"))])
async def list_expenses():
    return await db.expenses.find({}, {"_id": 0}).sort("date", -1).to_list(1000)

@api.post("/expenses")
@transactional
async def create_expense(body: Dict[str, Any], user: dict = Depends(require_module("finance"))):
    body["id"] = body.get("id") or new_id()
    body["created_at"] = now_iso()
    body["date"] = body.get("date") or now_iso()
    body["amount"] = positive(body.get("amount", 0), "Expense amount")
    await db.expenses.insert_one(body)
    await create_financial_transaction(user, "expense", body["amount"], body.get("account_id"), f"Expense: {body.get('description','')}", "expense", body["id"])
    await audit(user, "create", "expense", body["id"], None, body)
    body.pop("_id", None)
    return body

# ---------- SALES ORDER CANCEL ----------
@api.post("/sales_orders/{sid}/cancel")
@transactional
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

@api.put("/sales_orders/{sid}")
@transactional
async def update_sale(sid: str, body: Dict[str, Any], user: dict = Depends(require_module("sales"))):
    so = await db.sales_orders.find_one({"id": sid})
    if not so:
        raise HTTPException(404, "Order not found")
    if so.get("fulfillment_status") in {"completed", "shipped", "cancelled"} or so.get("settlement_id"):
        raise HTTPException(409, "Only open, unsettled sales orders can be edited")
    allowed = {"customer_name", "sales_channel", "discount", "voucher", "shipping", "other_fee", "advertising_cost",
               "live_video_fee_pct", "affiliate_fee_pct", "return_rate_pct", "payment_status", "fulfillment_status", "date"}
    if "items" in body or "customer_id" in body:
        raise HTTPException(400, "Item and customer changes require cancellation and a new order")
    changes = {key: value for key, value in body.items() if key in allowed}
    updated = {**so, **changes}
    subtotal = sum(float(item.get("quantity", 0)) * float(item.get("selling_price", 0)) for item in so.get("items", []))
    discount = nonnegative(updated.get("discount", 0), "Discount")
    voucher = nonnegative(updated.get("voucher", 0), "Voucher")
    shipping = nonnegative(updated.get("shipping", 0), "Shipping")
    fee_base = max(0, subtotal - discount - voucher)
    marketplace_fee = await calculate_marketplace_fee(updated.get("sales_channel", "Direct/Offline"), fee_base, updated.get("marketplace_fee"))
    other_fee = nonnegative(updated.get("other_fee", 0), "Other fee")
    advertising = nonnegative(updated.get("advertising_cost", 0), "Advertising cost")
    total = subtotal - discount - voucher + shipping
    updated.update({"subtotal": subtotal, "discount": discount, "voucher": voucher, "shipping": shipping,
                    "marketplace_fee": marketplace_fee, "other_fee": other_fee, "advertising_cost": advertising,
                    "total": total, "net_profit": total - marketplace_fee - other_fee - advertising - float(so.get("cogs", 0)),
                    "updated_at": now_iso()})
    await db.sales_orders.update_one({"id": sid}, {"$set": {key: value for key, value in updated.items() if key != "_id"}})
    await audit(user, "update", "sales_order", sid, so, updated)
    updated.pop("_id", None)
    return updated

@api.post("/sales_orders/{sid}/refund")
@transactional
async def refund_sale(sid: str, body: Dict[str, Any], user: dict = Depends(require_module("sales"))):
    so = await db.sales_orders.find_one({"id": sid})
    if not so:
        raise HTTPException(404, "Order not found")
    if so.get("fulfillment_status") == "cancelled":
        raise HTTPException(400, "Order already cancelled")
    order_total = float(so.get("total", 0))
    prior_refunds = await db.financial_transactions.find({"ref_type": "sales_refund", "ref_id": sid, "type": "expense"}).to_list(1000)
    refunded_before = float(so.get("refund_amount", 0)) or sum(float(txn.get("amount", 0)) for txn in prior_refunds)
    outstanding = order_total - refunded_before
    if outstanding <= 0:
        raise HTTPException(409, "Order already refunded")
    amount = positive(body.get("amount", outstanding), "Refund amount")
    if amount > outstanding:
        raise HTTPException(400, "Refund cannot exceed order total")
    prior = await db.financial_transactions.find_one({"ref_type": "sales_order", "ref_id": sid, "type": "income"})
    if prior:
        await create_financial_transaction(user, "expense", amount, prior.get("account_id"), f"Refund {so['order_number']}", "sales_refund", sid)
    refunded_total = refunded_before + amount
    await db.sales_orders.update_one({"id": sid}, {"$set": {"payment_status": "refunded" if refunded_total >= order_total else "partially_refunded", "refund_amount": refunded_total, "updated_at": now_iso()}})
    await audit(user, "refund", "sales_order", sid, so, {"amount": amount})
# ---------- UNIVERSAL IMPORT ENGINE & PREVIEW VALIDATOR ----------

IMPORT_TEMPLATES = {
    "products": {
        "filename": "template_products.csv",
        "csv": "name,sku,category,selling_price,cost,stock,color,size,min_stock\nKaos Polos Cotton Combed 30s,KPC-BLK-M,Pakaian,85000,45000,50,Hitam,M,10\nKaos Polos Cotton Combed 30s,KPC-BLK-L,Pakaian,85000,45000,40,Hitam,L,10\nKemeja Oxford Pria,KMO-WHT-XL,Pakaian,135000,75000,25,Putih,XL,5\n",
    },
    "materials": {
        "filename": "template_materials.csv",
        "csv": "name,sku,category,unit,cost,stock,min_stock\nKain Cotton Combed 30s Hitam,RAW-CC30-BLK,Kain,kg,110000,25.5,5.0\nBenang Jahit Poliester Hitam,RAW-BNG-BLK,Benang,roll,15000,100,20\nKancing Kemeja 18L Putih,RAW-KNC-WHT,Aksesoris,gross,25000,15,3\n",
    },
    "customers": {
        "filename": "template_customers.csv",
        "csv": "name,phone,email,address,customer_type\nBudi Santoso,081234567890,budi@example.com,Jl. Sudirman No. 10 Jakarta,vip\nSiti Nurhaliza,082345678901,siti@example.com,Jl. Merdeka No. 45 Bandung,new\nAndi Wijaya,085678901234,andi@example.com,Jl. Diponegoro No. 8 Surabaya,returning\n",
    },
    "suppliers": {
        "filename": "template_suppliers.csv",
        "csv": "name,contact_name,phone,email,address\nCV Tekstil Maju Jaya,Pak Hendra,081122334455,hendra@tekstilmaju.com,Kawasan Industri Cimahi Bandung\nPT Kancing Perkasa,Ibu Dewi,082233445566,dewi@kancingperkasa.co.id,Jl. Rungkut Industri Surabaya\n",
    },
    "sales_orders": {
        "filename": "template_sales_orders.csv",
        "csv": "order_number,date,customer_name,sales_channel,variant_sku,quantity,selling_price,discount,shipping,marketplace_fee,advertising_cost\nSP-2026-0001,2026-08-14,Rina Sari,Shopee,RDB-BL-M,2,89000,0,10000,15575,3000\nSP-2026-0002,2026-08-13,Budi Santoso,Shopee,RDB-WH-L,1,89000,5000,10000,7788,3000\nTT-2026-0001,2026-08-12,Andi Wijaya,TikTok Shop,RDC-BL-M,1,109000,0,10000,8720,3000\n",
    },
    "opening_balance": {
        "filename": "template_opening_balance.csv",
        "csv": "account_code,debit,credit\n1-10001,25000000,0\n1-10002,50000000,0\n2-10100,0,15000000\n3-10000,0,60000000\n",
    },
}

def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", "").replace("%", "").strip())
    except Exception:
        return default

@api.get("/imports/templates/{kind}")
@api.get("/imports/template/{kind}")
async def get_import_template(kind: str):
    kind_normalized = kind.lower().strip()
    if kind_normalized in ("orders", "sales", "marketplace"):
        kind_normalized = "sales_orders"
    tmpl = IMPORT_TEMPLATES.get(kind_normalized)
    if not tmpl:
        raise HTTPException(404, f"Template for '{kind}' not found. Available: {', '.join(IMPORT_TEMPLATES.keys())}")
    return Response(
        content=tmpl["csv"],
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{tmpl["filename"]}"'},
    )

class ImportPreviewIn(BaseModel):
    kind: str
    rows: List[Dict[str, Any]]

class ImportExecuteIn(BaseModel):
    kind: str
    rows: List[Dict[str, Any]]
    allow_partial: bool = False

async def validate_import_rows(kind: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    kind_normalized = kind.lower().strip()
    if kind_normalized in ("orders", "sales", "marketplace"):
        kind_normalized = "sales_orders"

    if kind_normalized not in IMPORT_TEMPLATES:
        raise HTTPException(400, f"Unsupported import type: '{kind}'. Allowed: {list(IMPORT_TEMPLATES.keys())}")

    if not rows:
        raise HTTPException(400, "Rows to import cannot be empty")

    validation_results = []
    seen_skus_batch = set()
    seen_order_numbers_batch = set()

    # Preload reference data for ultra-fast validation
    all_products = await db.products.find({"status": {"$ne": "archived"}}, {"_id": 0}).to_list(2000)
    sku_to_product = {}
    for p in all_products:
        for v in p.get("variants", []):
            if v.get("sku"):
                sku_to_product[v["sku"]] = {"product": p, "variant": v}

    all_materials = await db.materials.find({"status": {"$ne": "archived"}}, {"_id": 0}).to_list(2000)
    existing_mat_skus = {m.get("sku") for m in all_materials if m.get("sku")}
    existing_mat_names = {m.get("name", "").lower() for m in all_materials if m.get("name")}

    all_accounts = await db.accounts.find({"status": {"$ne": "archived"}}, {"_id": 0}).to_list(1000)
    accounts_by_code = {a.get("code"): a for a in all_accounts if a.get("code")}

    for idx, raw_row in enumerate(rows, start=1):
        errors = []
        warnings = []
        parsed = {}

        if kind_normalized == "products":
            name = str(raw_row.get("name") or raw_row.get("product_name") or "").strip()
            sku = str(raw_row.get("sku") or raw_row.get("variant_sku") or "").strip()
            category = str(raw_row.get("category") or raw_row.get("category_id") or "Pakaian").strip()
            selling_price = _coerce_float(raw_row.get("selling_price") or raw_row.get("price"), 0)
            cost = _coerce_float(raw_row.get("cost") or raw_row.get("hpp"), 0)
            stock = _coerce_float(raw_row.get("stock"), 0)
            min_stock = _coerce_float(raw_row.get("min_stock") or raw_row.get("minimum_stock"), 0)
            color = str(raw_row.get("color") or "-").strip()
            size = str(raw_row.get("size") or "-").strip()

            if not name:
                errors.append("Nama produk wajib diisi.")
            if not sku:
                errors.append("SKU varian produk wajib diisi.")
            elif sku in seen_skus_batch:
                errors.append(f"SKU '{sku}' duplikat dalam file import ini.")
            elif sku in sku_to_product:
                warnings.append(f"SKU '{sku}' sudah ada di database; stok/harga akan diperbarui.")

            if selling_price < 0:
                errors.append("Harga jual tidak boleh negatif.")
            if cost < 0:
                errors.append("HPP/Biaya pokok tidak boleh negatif.")
            if stock < 0:
                errors.append("Stok tidak boleh negatif.")

            seen_skus_batch.add(sku)
            parsed = {
                "name": name, "sku": sku, "category": category,
                "selling_price": selling_price, "cost": cost,
                "stock": stock, "min_stock": min_stock,
                "color": color, "size": size,
            }

        elif kind_normalized == "materials":
            name = str(raw_row.get("name") or raw_row.get("material_name") or "").strip()
            sku = str(raw_row.get("sku") or "").strip()
            category = str(raw_row.get("category") or "Bahan Baku").strip()
            unit = str(raw_row.get("unit") or "pcs").strip()
            cost = _coerce_float(raw_row.get("cost") or raw_row.get("unit_cost") or raw_row.get("price"), 0)
            stock = _coerce_float(raw_row.get("stock"), 0)
            min_stock = _coerce_float(raw_row.get("min_stock") or raw_row.get("minimum_stock"), 0)

            if not name:
                errors.append("Nama bahan baku wajib diisi.")
            if name.lower() in existing_mat_names:
                warnings.append(f"Bahan '{name}' sudah ada; data akan ditambahkan/diperbarui.")
            if sku and sku in existing_mat_skus:
                warnings.append(f"SKU bahan '{sku}' sudah ada di sistem.")
            if cost < 0:
                errors.append("Biaya satuan (cost) tidak boleh negatif.")
            if stock < 0:
                errors.append("Stok bahan tidak boleh negatif.")

            parsed = {
                "name": name, "sku": sku or f"MAT-{new_id()[:6].upper()}", "category": category,
                "unit": unit, "cost": cost, "stock": stock, "min_stock": min_stock,
            }

        elif kind_normalized == "customers":
            name = str(raw_row.get("name") or raw_row.get("customer_name") or "").strip()
            phone = str(raw_row.get("phone") or raw_row.get("kontak") or "").strip()
            email = str(raw_row.get("email") or "").strip()
            address = str(raw_row.get("address") or raw_row.get("alamat") or "").strip()
            customer_type = str(raw_row.get("customer_type") or raw_row.get("segment") or raw_row.get("channel") or "new").strip()

            if not name:
                errors.append("Nama pelanggan wajib diisi.")
            if email and "@" not in email:
                errors.append("Format email pelanggan tidak valid.")

            parsed = {
                "name": name, "phone": phone, "email": email, "address": address, "customer_type": customer_type,
            }

        elif kind_normalized == "suppliers":
            name = str(raw_row.get("name") or raw_row.get("supplier_name") or "").strip()
            contact_name = str(raw_row.get("contact_name") or raw_row.get("contact") or raw_row.get("pic") or "").strip()
            phone = str(raw_row.get("phone") or raw_row.get("kontak") or "").strip()
            email = str(raw_row.get("email") or "").strip()
            address = str(raw_row.get("address") or raw_row.get("alamat") or "").strip()

            if not name:
                errors.append("Nama supplier/vendor wajib diisi.")
            if email and "@" not in email:
                errors.append("Format email supplier tidak valid.")

            parsed = {
                "name": name, "contact_name": contact_name, "phone": phone, "email": email, "address": address,
            }

        elif kind_normalized == "sales_orders":
            sku = str(raw_row.get("variant_sku") or raw_row.get("sku") or "").strip()
            qty = _coerce_float(raw_row.get("quantity") or raw_row.get("qty"), 1)
            price = _coerce_float(raw_row.get("selling_price") or raw_row.get("price"), 0)
            order_number = str(raw_row.get("order_number") or raw_row.get("invoice") or "").strip()
            customer_name = str(raw_row.get("customer_name") or raw_row.get("buyer") or "Marketplace Buyer").strip()
            sales_channel = str(raw_row.get("sales_channel") or raw_row.get("channel") or "Shopee").strip()
            discount = _coerce_float(raw_row.get("discount"), 0)
            shipping = _coerce_float(raw_row.get("shipping"), 0)
            mp_fee = _coerce_float(raw_row.get("marketplace_fee") or raw_row.get("fee"), 0)
            ad_cost = _coerce_float(raw_row.get("advertising_cost") or raw_row.get("ads"), 0)
            date_val = str(raw_row.get("date") or "").strip() or now_iso()

            if not sku:
                errors.append("SKU varian wajib diisi.")
            elif sku not in sku_to_product:
                errors.append(f"SKU '{sku}' tidak ditemukan di katalog produk.")
            else:
                curr_stock = float(sku_to_product[sku]["variant"].get("stock", 0))
                if curr_stock < qty:
                    warnings.append(f"Stok SKU '{sku}' tersisa {curr_stock}, penjualan sebesar {qty} akan menyebabkan minus.")

            if qty <= 0:
                errors.append("Jumlah (quantity) harus lebih besar dari 0.")
            if price < 0:
                errors.append("Harga jual tidak boleh negatif.")

            if order_number:
                if order_number in seen_order_numbers_batch:
                    warnings.append(f"No order '{order_number}' duplikat dalam batch ini (akan digabung / dibuat item baru).")
                seen_order_numbers_batch.add(order_number)

            parsed = {
                "order_number": order_number, "date": date_val,
                "customer_name": customer_name, "sales_channel": sales_channel,
                "variant_sku": sku, "quantity": qty, "selling_price": price,
                "discount": discount, "shipping": shipping,
                "marketplace_fee": mp_fee, "advertising_cost": ad_cost,
            }

        elif kind_normalized == "opening_balance":
            code = str(raw_row.get("account_code") or raw_row.get("code") or "").strip()
            debit = _coerce_float(raw_row.get("debit"), 0)
            credit = _coerce_float(raw_row.get("credit"), 0)

            if not code:
                errors.append("Kode akun COA wajib diisi.")
            elif code not in accounts_by_code:
                errors.append(f"Kode akun '{code}' tidak terdaftar di Chart of Accounts.")

            if debit < 0 or credit < 0:
                errors.append("Nilai debit/credit tidak boleh negatif.")
            if debit == 0 and credit == 0:
                errors.append("Setidaknya debit atau credit harus lebih besar dari 0.")
            if debit > 0 and credit > 0:
                errors.append("Satu baris tidak boleh memiliki debit dan credit sekaligus.")

            parsed = {
                "account_code": code,
                "account_id": accounts_by_code.get(code, {}).get("id", ""),
                "account_name": accounts_by_code.get(code, {}).get("name", ""),
                "debit": debit,
                "credit": credit,
            }

        is_valid = len(errors) == 0
        validation_results.append({
            "row_index": idx,
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "raw": raw_row,
            "parsed": parsed,
        })

    valid_count = sum(1 for r in validation_results if r["is_valid"])
    invalid_count = len(validation_results) - valid_count

    return {
        "ok": True,
        "kind": kind_normalized,
        "total": len(validation_results),
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "is_all_valid": invalid_count == 0,
        "rows": validation_results,
    }

@api.post("/imports/preview")
async def preview_import(body: ImportPreviewIn, user: dict = Depends(get_current_user)):
    return await validate_import_rows(body.kind, body.rows)

@api.post("/imports/execute")
@transactional
async def execute_import(body: ImportExecuteIn, user: dict = Depends(get_current_user)):
    validation = await validate_import_rows(body.kind, body.rows)
    kind = validation["kind"]

    if not body.allow_partial and not validation["is_all_valid"]:
        first_err = next(r for r in validation["rows"] if not r["is_valid"])
        raise HTTPException(
            status_code=400,
            detail=f"Import dibatalkan (Strict Mode): Baris #{first_err['row_index']} gagal validasi: {'; '.join(first_err['errors'])}",
        )

    rows_to_process = [r["parsed"] for r in validation["rows"] if r["is_valid"]]
    if not rows_to_process:
        raise HTTPException(400, "Tidak ada data valid yang dapat diimpor.")

    created_count = 0
    updated_count = 0

    if kind == "products":
        for item in rows_to_process:
            sku = item["sku"]
            existing = await db.products.find_one({"variants.sku": sku})
            if existing:
                # update variant stock and price
                variants = existing.get("variants", [])
                for v in variants:
                    if v.get("sku") == sku:
                        before = float(v.get("stock", 0))
                        v["stock"] = item["stock"]
                        v["cost"] = item["cost"]
                        v["selling_price"] = item["selling_price"]
                        v["color"] = item["color"]
                        v["size"] = item["size"]
                        break
                await db.products.update_one({"id": existing["id"]}, {"$set": {"variants": variants, "updated_at": now_iso()}})
                if item["stock"] > 0:
                    await record_movement("product", existing["id"], sku, item["stock"] - before, "initial", before, item["stock"], user["id"], "Import Product Stock Update")
                updated_count += 1
            else:
                # Check if product with same name exists
                prod_by_name = await db.products.find_one({"name": item["name"], "status": {"$ne": "archived"}})
                variant_obj = {
                    "sku": sku,
                    "color": item["color"],
                    "size": item["size"],
                    "stock": item["stock"],
                    "cost": item["cost"],
                    "selling_price": item["selling_price"],
                }
                if prod_by_name:
                    prod_by_name["variants"].append(variant_obj)
                    await db.products.update_one({"id": prod_by_name["id"]}, {"$set": {"variants": prod_by_name["variants"], "updated_at": now_iso()}})
                    if item["stock"] > 0:
                        await record_movement("product", prod_by_name["id"], sku, item["stock"], "initial", 0, item["stock"], user["id"], "Import Product Variant")
                    updated_count += 1
                else:
                    pid = new_id()
                    doc = {
                        "id": pid,
                        "name": item["name"],
                        "sku": sku,
                        "category_id": item["category"],
                        "brand": "NexaBiz",
                        "status": "active",
                        "minimum_stock": item["min_stock"],
                        "cost": item["cost"],
                        "selling_price": item["selling_price"],
                        "variants": [variant_obj],
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                    }
                    await db.products.insert_one(doc)
                    if item["stock"] > 0:
                        await record_movement("product", pid, sku, item["stock"], "initial", 0, item["stock"], user["id"], "Import Product")
                    created_count += 1
        await audit(user, "import", "products", f"batch_{len(rows_to_process)}", None, {"created": created_count, "updated": updated_count})

    elif kind == "materials":
        for item in rows_to_process:
            mid = new_id()
            doc = {
                "id": mid,
                "name": item["name"],
                "sku": item["sku"],
                "category": item["category"],
                "unit": item["unit"],
                "cost": item["cost"],
                "stock": item["stock"],
                "minimum_stock": item["min_stock"],
                "status": "active",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            await db.materials.insert_one(doc)
            if item["stock"] > 0:
                await record_movement("material", mid, "initial", item["stock"], "initial", 0, item["stock"], user["id"], "Import Material Stock")
            created_count += 1
        await audit(user, "import", "materials", f"batch_{len(rows_to_process)}", None, {"created": created_count})

    elif kind == "customers":
        for item in rows_to_process:
            cid = new_id()
            doc = {
                "id": cid,
                "name": item["name"],
                "phone": item["phone"],
                "email": item["email"],
                "address": item["address"],
                "customer_type": item["customer_type"],
                "total_orders": 0,
                "total_spending": 0,
                "status": "active",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            await db.customers.insert_one(doc)
            created_count += 1
        await audit(user, "import", "customers", f"batch_{len(rows_to_process)}", None, {"created": created_count})

    elif kind == "suppliers":
        for item in rows_to_process:
            sid = new_id()
            doc = {
                "id": sid,
                "name": item["name"],
                "contact_name": item["contact_name"],
                "phone": item["phone"],
                "email": item["email"],
                "address": item["address"],
                "status": "active",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            await db.suppliers.insert_one(doc)
            created_count += 1
        await audit(user, "import", "suppliers", f"batch_{len(rows_to_process)}", None, {"created": created_count})

    elif kind == "sales_orders":
        for item in rows_to_process:
            sku = item["variant_sku"]
            qty = item["quantity"]
            prod = await db.products.find_one({"variants.sku": sku})
            if not prod:
                continue
            variant = next(v for v in prod["variants"] if v["sku"] == sku)
            before = float(variant.get("stock", 0))
            after = before - qty
            variant["stock"] = after
            await db.products.update_one({"id": prod["id"]}, {"$set": {"variants": prod["variants"], "updated_at": now_iso()}})

            subtotal = item["selling_price"] * qty
            cogs = float(variant.get("cost", 0)) * qty
            total = subtotal - item["discount"] + item["shipping"]
            net = total - item["marketplace_fee"] - item["advertising_cost"] - cogs

            sid = new_id()
            onum = item["order_number"] or f"SO-IMP-{datetime.now().strftime('%y%m%d')}-{sid[:4].upper()}"
            so_doc = {
                "id": sid,
                "order_number": onum,
                "date": item["date"],
                "customer_name": item["customer_name"],
                "sales_channel": item["sales_channel"],
                "items": [{
                    "product_id": prod["id"],
                    "product_name": prod["name"],
                    "variant_sku": sku,
                    "quantity": qty,
                    "selling_price": item["selling_price"],
                    "cost": float(variant.get("cost", 0)),
                }],
                "subtotal": subtotal,
                "cogs": cogs,
                "discount": item["discount"],
                "voucher": 0,
                "shipping": item["shipping"],
                "marketplace_fee": item["marketplace_fee"],
                "other_fee": 0,
                "advertising_cost": item["advertising_cost"],
                "total": total,
                "net_profit": net,
                "payment_status": "paid",
                "fulfillment_status": "completed",
                "imported": True,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            await db.sales_orders.insert_one(so_doc)
            await record_movement("product", prod["id"], sku, -qty, "sales", before, after, user["id"], f"Import {onum}")
            created_count += 1
        await audit(user, "import", "sales_orders", f"batch_{len(rows_to_process)}", None, {"created": created_count})

    elif kind == "opening_balance":
        lines_payload = []
        for item in rows_to_process:
            lines_payload.append(OpeningBalanceLine(
                account_id=item["account_id"],
                debit=item["debit"],
                credit=item["credit"],
            ))
        ob_in = OpeningBalanceIn(
            as_of_date=datetime.now(timezone.utc).isoformat()[:10],
            lines=lines_payload,
            auto_balance=True,
        )
        res = await save_opening_balance(ob_in, user)
        created_count = len(lines_payload)
        await audit(user, "import", "opening_balance", f"batch_{len(rows_to_process)}", None, {"accounts_updated": created_count, "total": res.get("total")})

    return {
        "ok": True,
        "kind": kind,
        "created": created_count,
        "updated": updated_count,
        "skipped": [r for r in validation["rows"] if not r["is_valid"]],
    }

# Backward compatibility routes
@api.post("/imports/csv")
async def import_csv_rows_compat(body: Dict[str, Any], user: dict = Depends(get_current_user)):
    kind = str(body.get("kind", "")).lower()
    rows = body.get("rows") or []
    return await execute_import(ImportExecuteIn(kind=kind, rows=rows, allow_partial=True), user)

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
@transactional
async def import_marketplace_orders(body: BulkImportIn, user: dict = Depends(require_module("sales"))):
    raw_rows = [o.model_dump() for o in body.orders]
    exec_res = await execute_import(ImportExecuteIn(kind="sales_orders", rows=raw_rows, allow_partial=True), user)
    return {
        "created": exec_res["created"],
        "skipped": [{"sku": s["parsed"].get("variant_sku"), "reason": "; ".join(s["errors"])} for s in exec_res.get("skipped", [])],
    }



# ---------- MARKETPLACE SETTLEMENT ----------
@api.get("/marketplace/settlements", dependencies=[Depends(require_module("finance"))])
async def list_settlements():
    return await db.marketplace_settlements.find({}, {"_id": 0}).sort("settled_at", -1).to_list(500)


@api.post("/marketplace/settlements")
@transactional
async def create_settlement(body: Dict[str, Any], user: dict = Depends(require_module("finance"))):
    order_ids = body.get("order_ids") or []
    if not order_ids:
        raise HTTPException(400, "At least one marketplace order is required")
    orders = await db.sales_orders.find({"id": {"$in": order_ids}}, {"_id": 0}).to_list(1000)
    if len(orders) != len(set(order_ids)):
        raise HTTPException(400, "One or more sales orders were not found")
    if any(not is_marketplace_channel(o.get("sales_channel", "")) for o in orders):
        raise HTTPException(400, "Only marketplace orders can be settled")
    if any(o.get("settlement_id") for o in orders):
        raise HTTPException(400, "One or more orders are already settled")
    gross = sum(float(o.get("total", 0)) for o in orders)
    recorded_fees = sum(float(o.get("marketplace_fee", 0)) + float(o.get("other_fee", 0)) + float(o.get("advertising_cost", 0)) for o in orders)
    net_amount = positive(body.get("net_amount", gross - recorded_fees), "Settlement amount")
    account_id = body.get("account_id") or await get_default_account_id()
    if not account_id or not await db.accounts.find_one({"id": account_id}):
        raise HTTPException(400, "Settlement account not found")
    settlement_id = new_id()
    settlement = {
        "id": settlement_id,
        "settlement_number": body.get("settlement_number") or f"SET-{datetime.now().strftime('%y%m%d')}-{settlement_id[:4].upper()}",
        "sales_channel": body.get("sales_channel") or orders[0].get("sales_channel"),
        "order_ids": order_ids, "order_count": len(orders), "gross": gross,
        "recorded_fees": recorded_fees, "net_amount": net_amount,
        "account_id": account_id, "settled_at": body.get("settled_at") or now_iso(),
        "created_at": now_iso(), "user_id": user["id"],
    }
    await db.marketplace_settlements.insert_one(settlement)
    await create_financial_transaction(user, "income", net_amount, account_id, f"Settlement {settlement['settlement_number']}", "marketplace_settlement", settlement_id)
    await db.sales_orders.update_many({"id": {"$in": order_ids}}, {"$set": {"settlement_id": settlement_id, "settlement_status": "settled", "updated_at": now_iso()}})
    await audit(user, "create", "marketplace_settlement", settlement_id, None, settlement)
    settlement.pop("_id", None)
    return settlement


# ---------- RETURNS ----------
@api.get("/returns", dependencies=[Depends(require_module("sales"))])
async def list_returns():
    return await db.returns.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/returns")
@transactional
async def create_return(body: Dict[str, Any], user: dict = Depends(require_module("sales"))):
    sales_order_id = body.get("sales_order_id")
    sales_order = await db.sales_orders.find_one({"id": sales_order_id})
    if not sales_order:
        raise HTTPException(404, "Sales order not found")
    quantity = positive(body.get("quantity", 0), "Return quantity")
    item = next((item for item in sales_order.get("items", []) if item.get("variant_sku") == body.get("variant_sku")), None)
    if not item or quantity > float(item.get("quantity", 0)):
        raise HTTPException(400, "Return quantity exceeds the sold quantity")
    active_returns = await db.returns.find({"sales_order_id": sales_order_id, "variant_sku": body.get("variant_sku"), "status": {"$ne": "cancelled"}}).to_list(1000)
    returned_before = sum(float(existing.get("quantity", 0)) for existing in active_returns)
    if returned_before + quantity > float(item.get("quantity", 0)):
        raise HTTPException(400, "Total returned quantity exceeds the sold quantity")
    condition = str(body.get("condition", "good")).lower()
    if condition not in {"good", "resalable", "damaged", "defective"}:
        raise HTTPException(400, "Invalid return condition")
    line_total = float(item.get("selling_price", 0)) * float(item.get("quantity", 0))
    refunded_before = sum(float(existing.get("refund_amount", 0)) for existing in active_returns)
    refund_amount = nonnegative(body.get("refund_amount", 0), "Refund amount")
    if refund_amount > line_total - refunded_before:
        raise HTTPException(400, "Total refund exceeds the sold item amount")
    cogs_reversal = float(item.get("cost", 0)) * quantity if condition in {"good", "resalable"} else 0
    return_id = new_id()
    return_doc = {"id": return_id, "sales_order_id": sales_order_id, "variant_sku": body.get("variant_sku"), "quantity": quantity,
                  "condition": condition, "reason": body.get("reason", ""), "refund_amount": refund_amount,
                  "cogs_reversal": cogs_reversal,
                  "status": "received", "created_at": now_iso(), "user_id": user["id"]}
    if condition in {"good", "resalable"}:
        product = await db.products.find_one({"id": item["product_id"]})
        if product:
            variants = product.get("variants", [])
            variant = next((variant for variant in variants if variant.get("sku") == item.get("variant_sku")), None)
            if variant:
                before = float(variant.get("stock", 0)); variant["stock"] = before + quantity
                await db.products.update_one({"id": product["id"]}, {"$set": {"variants": variants, "updated_at": now_iso()}})
                await record_movement("product", product["id"], item["variant_sku"], quantity, "return", before, variant["stock"], user["id"], f"Return {sales_order['order_number']}")
        if cogs_reversal:
            new_cogs = max(0, float(sales_order.get("cogs", 0)) - cogs_reversal)
            await db.sales_orders.update_one({"id": sales_order_id}, {"$set": {
                "cogs": new_cogs,
                "net_profit": float(sales_order.get("net_profit", 0)) + cogs_reversal,
                "updated_at": now_iso(),
            }})
    await db.returns.insert_one(return_doc)
    if return_doc["refund_amount"] > 0:
        prior = await db.financial_transactions.find_one({"ref_type": "sales_order", "ref_id": sales_order_id, "type": "income"})
        if prior:
            await create_financial_transaction(user, "expense", return_doc["refund_amount"], prior.get("account_id"), f"Refund {sales_order['order_number']}", "return", return_id)
    await audit(user, "create", "return", return_id, None, return_doc)
    return_doc.pop("_id", None)
    return return_doc

# ---------- ONBOARDING ----------
class OnboardingIn(BaseModel):
    business_name: str
    currency: str = "USD"
    locale: str = "en-US"
    timezone: str = "UTC"
    tax_enabled: bool = False
    tax_name: str = "Tax"
    tax_rate: float = 0
    tax_inclusive: bool = False
    initial_capital: float = 0
    account_name: str = "Kas Tunai"

@api.post("/onboarding/complete")
@transactional
async def complete_onboarding(body: OnboardingIn, user: dict = Depends(require_role("owner"))):
    # save business profile
    await db.settings_kv.update_one(
        {"id": "business_profile"},
        {"$set": {"id": "business_profile", **body.model_dump(exclude={"initial_capital", "account_name"}), "setup_complete": True, "updated_at": now_iso()}},
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

@api.get("/settings/business-profile")
async def get_business_profile(user: dict = Depends(get_current_user)):
    doc = await db.settings_kv.find_one({"id": "business_profile"}, {"_id": 0})
    return doc or {"business_name": "NexaBiz Business", "currency": "USD", "locale": "en-US", "timezone": "UTC", "tax_enabled": False, "tax_name": "Tax", "tax_rate": 0, "tax_inclusive": False}

@api.get("/settings/backup-status")
async def backup_status(user: dict = Depends(require_role("owner"))):
    if not BACKUPS_DIR.exists():
        return {"available": False, "backup_count": 0, "latest": None, "warning": "No backup has been created yet."}
    candidates = [item for item in BACKUPS_DIR.iterdir() if item.is_dir()]
    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    latest = candidates[0] if candidates else None
    latest_at = datetime.fromtimestamp(latest.stat().st_mtime, timezone.utc).isoformat() if latest else None
    age_hours = ((datetime.now(timezone.utc) - datetime.fromtimestamp(latest.stat().st_mtime, timezone.utc)).total_seconds() / 3600) if latest else None
    warning = None if age_hours is not None and age_hours <= 24 else "Backup is older than 24 hours."
    return {"available": bool(latest), "backup_count": len(candidates), "latest": latest.name if latest else None, "latest_at": latest_at, "age_hours": round(age_hours, 1) if age_hours is not None else None, "warning": warning}

@api.put("/settings/business-profile")
@transactional
async def update_business_profile(body: OnboardingIn, user: dict = Depends(require_role("owner"))):
    existing = await db.settings_kv.find_one({"id": "business_profile"}, {"_id": 0})
    profile = {"id": "business_profile", **body.model_dump(exclude={"initial_capital", "account_name"}), "setup_complete": True, "updated_at": now_iso()}
    await db.settings_kv.update_one({"id": "business_profile"}, {"$set": profile}, upsert=True)
    await audit(user, "update", "business_profile", "business_profile", existing, profile)
    return profile

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
async def export_sales_csv(user: dict = Depends(require_module("sales"))):
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


class DTFCostingIn(BaseModel):
    design_name: str = ""
    quantity: float = 1
    blank_cost: float = 0
    dtf_transfer_cost: float = 0
    printing_cost: float = 0
    labor_cost: float = 0
    packaging_cost: float = 0
    design_setup_cost: float = 0
    reject_rate: float = 0
    selling_price: float = 0


async def calculate_dtf_costing(body: Dict[str, Any], user: Optional[dict] = None):
    quantity = positive(body.get("quantity", 0), "Quantity")
    reject_rate = nonnegative(body.get("reject_rate", 0), "Reject rate")
    if reject_rate > 1:
        raise HTTPException(400, "Reject rate cannot exceed 100%")

    design_name = (body.get("design_name") or "Custom DTF Design").strip() or "Custom DTF Design"
    blank_cost = nonnegative(body.get("blank_cost", 0), "Blank cost")
    dtf_transfer_cost = nonnegative(body.get("dtf_transfer_cost", 0), "DTF transfer cost")
    printing_cost = nonnegative(body.get("printing_cost", 0), "Printing cost")
    labor_cost = nonnegative(body.get("labor_cost", 0), "Labor cost")
    packaging_cost = nonnegative(body.get("packaging_cost", 0), "Packaging cost")
    design_setup_cost = nonnegative(body.get("design_setup_cost", 0), "Design setup cost")
    selling_price = nonnegative(body.get("selling_price", 0), "Selling price")

    reject_qty = quantity * reject_rate
    produced_qty = quantity + reject_qty
    variable_cost_per_unit = blank_cost + dtf_transfer_cost + printing_cost + labor_cost + packaging_cost
    total_variable_cost = variable_cost_per_unit * produced_qty
    total_cost = total_variable_cost + design_setup_cost
    unit_cost = total_cost / quantity if quantity > 0 else 0

    fallback_suggested_price = max(unit_cost * 1.25, unit_cost + 10000)
    suggested_price = selling_price if selling_price > 0 else fallback_suggested_price
    gross_profit = suggested_price - unit_cost
    margin_percent = (gross_profit / suggested_price * 100) if suggested_price > 0 else 0

    return {
        "design_name": design_name,
        "quantity": quantity,
        "reject_qty": round(reject_qty, 2),
        "produced_qty": round(produced_qty, 2),
        "unit_cost": round(unit_cost, 2),
        "total_cost": round(total_cost, 2),
        "gross_profit": round(gross_profit, 2),
        "suggested_price": round(suggested_price, 2),
        "margin_percent": round(margin_percent, 2),
        "cost_breakdown": {
            "blank_cost": round(blank_cost * produced_qty, 2),
            "dtf_transfer_cost": round(dtf_transfer_cost * produced_qty, 2),
            "printing_cost": round(printing_cost * produced_qty, 2),
            "labor_cost": round(labor_cost * produced_qty, 2),
            "packaging_cost": round(packaging_cost * produced_qty, 2),
            "design_setup_cost": round(design_setup_cost, 2),
            "reject_cost": round((blank_cost + dtf_transfer_cost + printing_cost + labor_cost + packaging_cost) * reject_qty, 2),
        },
    }


@api.post("/dtf/costing", dependencies=[Depends(require_module("production"))])
async def dtf_costing(body: DTFCostingIn):
    return await calculate_dtf_costing(body.model_dump())

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

@api.get("/search")
async def global_search(q: str, user: dict = Depends(get_current_user)):
    query = q.strip()
    if len(query) < 2:
        return []
    pattern = {"$regex": re.escape(query), "$options": "i"}
    results = []
    for collection, entity_type, fields in [
        ("products", "product", ["name", "sku"]), ("customers", "customer", ["name", "email", "phone"]),
        ("suppliers", "supplier", ["name", "email", "phone"]), ("sales_orders", "sales_order", ["order_number", "customer_name"]),
        ("purchase_orders", "purchase_order", ["po_number"]), ("production_orders", "production_order", ["prod_number", "product_name"]),
    ]:
        criteria = [{field: pattern} for field in fields]
        rows = await db[collection].find({"$or": criteria, "status": {"$ne": "archived"}}, {"_id": 0}).to_list(20)
        for row in rows:
            results.append({"type": entity_type, "id": row.get("id"), "label": row.get("name") or row.get("order_number") or row.get("po_number") or row.get("prod_number"), "detail": row.get("sku") or row.get("customer_name") or row.get("product_name") or ""})
    return results[:50]

@api.get("/notifications")
async def notifications(user: dict = Depends(get_current_user)):
    products = await db.products.find({"status": {"$ne": "archived"}}, {"_id": 0}).to_list(1000)
    materials = await db.materials.find({"status": {"$ne": "archived"}}, {"_id": 0}).to_list(1000)
    notifications = []
    for product in products:
        for variant in product.get("variants", []):
            stock = float(variant.get("stock", 0))
            minimum = float(product.get("minimum_stock", 0))
            if stock <= minimum:
                notifications.append({"type": "low_stock", "severity": "critical" if stock == 0 else "warning", "message": f"{product.get('name', '')} {variant.get('sku', '')} stok {stock}"})
    for material in materials:
        stock = float(material.get("stock", 0))
        if stock <= float(material.get("minimum_stock", 0)):
            notifications.append({"type": "low_stock", "severity": "critical" if stock == 0 else "warning", "message": f"Bahan {material.get('name', '')} stok {stock}"})
    pending = await db.purchase_orders.count_documents({"received_status": "pending"})
    if pending:
        notifications.append({"type": "pending_purchase", "severity": "info", "message": f"{pending} purchase order menunggu penerimaan"})
    return {"count": len(notifications), "items": notifications[:50]}

class ReconciliationIn(BaseModel):
    account_id: str
    actual_balance: float
    notes: str = ""

@api.post("/finance/reconcile")
@transactional
async def reconcile_account(body: ReconciliationIn, user: dict = Depends(require_module("finance"))):
    actual = nonnegative(body.actual_balance, "Actual balance")
    account = await db.accounts.find_one({"id": body.account_id})
    if not account:
        raise HTTPException(404, "Financial account not found")
    system_balance = float(account.get("balance", 0))
    result = {"account_id": body.account_id, "system_balance": system_balance, "actual_balance": actual, "difference": actual - system_balance, "notes": body.notes}
    await db.reconciliations.insert_one({"id": new_id(), **result, "user_id": user["id"], "created_at": now_iso()})
    await audit(user, "reconcile", "account", body.account_id, {"balance": system_balance}, result)
    return result

@api.get("/finance/reconciliations")
async def list_reconciliations(user: dict = Depends(require_module("finance"))):
    return await db.reconciliations.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)

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


@api.get("/reports/balance_sheet", dependencies=[Depends(require_module("reports"))])
async def report_balance_sheet(as_of_date: str = ""):
    as_of = as_of_date or datetime.now(timezone.utc).isoformat()[:10]
    cutoff_iso = f"{as_of}T23:59:59Z" if len(as_of) == 10 else as_of
    
    accounts = await db.accounts.find({"status": {"$ne": "archived"}}, {"_id": 0}).sort("code", 1).to_list(1000)
    
    sales = await db.sales_orders.find({"date": {"$lte": cutoff_iso}}, {"_id": 0}).to_list(10000)
    expenses = await db.expenses.find({"date": {"$lte": cutoff_iso}}, {"_id": 0}).to_list(10000)
    revenue = sum(float(s.get("total", 0)) for s in sales)
    cogs = sum(float(s.get("cogs", 0)) for s in sales)
    mp_fees = sum(float(s.get("marketplace_fee", 0)) for s in sales)
    adv = sum(float(s.get("advertising_cost", 0)) for s in sales)
    op_exp = sum(float(e.get("amount", 0)) for e in expenses)
    current_net_profit = revenue - cogs - mp_fees - adv - op_exp
    
    current_assets = []
    fixed_assets = []
    current_liabilities = []
    long_term_liabilities = []
    equity_items = []
    
    total_current_assets = 0.0
    total_fixed_assets = 0.0
    total_current_liabilities = 0.0
    total_long_term_liabilities = 0.0
    total_equity_nominal = 0.0
    
    for acc in accounts:
        atype = acc.get("account_type", "asset")
        stype = acc.get("subtype", "")
        bal = float(acc.get("balance", 0))
        
        if atype == "asset":
            if stype == "Aset Tetap":
                is_contra = acc.get("normal_balance") == "credit"
                amount = -bal if is_contra else bal
                fixed_assets.append({**acc, "amount": amount})
                total_fixed_assets += amount
            else:
                current_assets.append({**acc, "amount": bal})
                total_current_assets += bal
        elif atype == "liability":
            if stype == "Kewajiban Jangka Panjang":
                long_term_liabilities.append({**acc, "amount": bal})
                total_long_term_liabilities += bal
            else:
                current_liabilities.append({**acc, "amount": bal})
                total_current_liabilities += bal
        elif atype == "equity":
            equity_items.append({**acc, "amount": bal})
            total_equity_nominal += bal
            
    equity_items.append({
        "code": "3-10999",
        "name": "Laba Periode Berjalan",
        "account_type": "equity",
        "subtype": "Ekuitas",
        "amount": current_net_profit,
        "is_system": True
    })
    total_equity = total_equity_nominal + current_net_profit
    
    total_assets = total_current_assets + total_fixed_assets
    total_liabilities = total_current_liabilities + total_long_term_liabilities
    total_liabilities_and_equity = total_liabilities + total_equity
    diff = round(total_assets - total_liabilities_and_equity, 2)
    
    return {
        "as_of_date": as_of,
        "current_assets": current_assets,
        "total_current_assets": total_current_assets,
        "fixed_assets": fixed_assets,
        "total_fixed_assets": total_fixed_assets,
        "total_assets": total_assets,
        "current_liabilities": current_liabilities,
        "total_current_liabilities": total_current_liabilities,
        "long_term_liabilities": long_term_liabilities,
        "total_long_term_liabilities": total_long_term_liabilities,
        "total_liabilities": total_liabilities,
        "equity": equity_items,
        "total_equity": total_equity,
        "total_liabilities_and_equity": total_liabilities_and_equity,
        "difference": diff,
        "is_balanced": abs(diff) < 1.0,
    }


@api.get("/reports/trial_balance", dependencies=[Depends(require_module("reports"))])
async def report_trial_balance(as_of_date: str = ""):
    as_of = as_of_date or datetime.now(timezone.utc).isoformat()[:10]
    cutoff_iso = f"{as_of}T23:59:59Z" if len(as_of) == 10 else as_of
    
    accounts = await db.accounts.find({"status": {"$ne": "archived"}}, {"_id": 0}).sort("code", 1).to_list(1000)
    journals = await db.journal_entries.find({"date": {"$lte": cutoff_iso}}, {"_id": 0}).to_list(10000)
    
    lines_by_acc = {}
    for j in journals:
        for line in j.get("lines", []):
            acc_id = line.get("account_id")
            if acc_id:
                lines_by_acc.setdefault(acc_id, {"debit": 0.0, "credit": 0.0})
                lines_by_acc[acc_id]["debit"] += float(line.get("debit", 0))
                lines_by_acc[acc_id]["credit"] += float(line.get("credit", 0))
                
    rows = []
    total_debit = 0.0
    total_credit = 0.0
    
    for acc in accounts:
        act = lines_by_acc.get(acc["id"], {"debit": float(acc.get("opening_debit", 0)), "credit": float(acc.get("opening_credit", 0))})
        if acc["id"] not in lines_by_acc and float(acc.get("balance", 0)) > 0:
            if acc.get("normal_balance") == "credit":
                act["credit"] = max(act["credit"], float(acc["balance"]))
            else:
                act["debit"] = max(act["debit"], float(acc["balance"]))
                
        d = round(act["debit"], 2)
        c = round(act["credit"], 2)
        if d > 0 or c > 0:
            total_debit += d
            total_credit += c
            rows.append({
                "account_id": acc["id"],
                "code": acc.get("code", "-"),
                "name": acc.get("name", ""),
                "account_type": acc.get("account_type", "asset"),
                "subtype": acc.get("subtype", ""),
                "normal_balance": acc.get("normal_balance", "debit"),
                "debit": d,
                "credit": c,
            })
            
    diff = round(total_debit - total_credit, 2)
    return {
        "as_of_date": as_of,
        "rows": rows,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "difference": diff,
        "is_balanced": abs(diff) < 0.01,
    }


@api.get("/reports/general_ledger", dependencies=[Depends(require_module("reports"))])
async def report_general_ledger(account_id: str, start: str = "", end: str = ""):
    acc = await db.accounts.find_one({"$or": [{"id": account_id}, {"code": account_id}]}, {"_id": 0})
    if not acc:
        raise HTTPException(404, "Account not found")
        
    query = {"lines.account_id": acc["id"]}
    if start: query.setdefault("date", {})["$gte"] = start
    if end: query.setdefault("date", {})["$lte"] = f"{end}T23:59:59Z" if len(end) == 10 else end
    
    entries = await db.journal_entries.find(query, {"_id": 0}).sort("date", 1).to_list(10000)
    
    running_balance = 0.0
    transactions = []
    normal = acc.get("normal_balance", "debit")
    
    for e in entries:
        for line in e.get("lines", []):
            if line.get("account_id") == acc["id"]:
                d = float(line.get("debit", 0))
                c = float(line.get("credit", 0))
                if normal == "debit":
                    running_balance += (d - c)
                else:
                    running_balance += (c - d)
                transactions.append({
                    "date": e.get("date", "")[:10],
                    "reference": e.get("reference", "-"),
                    "description": line.get("description") or e.get("description", ""),
                    "source_type": e.get("source_type", "manual"),
                    "debit": d,
                    "credit": c,
                    "running_balance": round(running_balance, 2),
                })
                
    total_debit = sum(t["debit"] for t in transactions)
    total_credit = sum(t["credit"] for t in transactions)
    
    return {
        "account": acc,
        "transactions": transactions,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "ending_balance": round(running_balance, 2),
    }


@api.get("/reports/export/balance_sheet")
async def export_balance_sheet_csv(as_of_date: str = "", user: dict = Depends(require_module("reports"))):
    data = await report_balance_sheet(as_of_date)
    rows = []
    rows.append({"category": "ASSETS", "code": "", "name": "--- ASET LANCAR ---", "amount": ""})
    for a in data["current_assets"]:
        rows.append({"category": "Current Asset", "code": a.get("code", ""), "name": a.get("name", ""), "amount": a.get("amount", 0)})
    rows.append({"category": "", "code": "", "name": "TOTAL ASET LANCAR", "amount": data["total_current_assets"]})
    
    rows.append({"category": "ASSETS", "code": "", "name": "--- ASET TETAP ---", "amount": ""})
    for a in data["fixed_assets"]:
        rows.append({"category": "Fixed Asset", "code": a.get("code", ""), "name": a.get("name", ""), "amount": a.get("amount", 0)})
    rows.append({"category": "", "code": "", "name": "TOTAL ASET TETAP", "amount": data["total_fixed_assets"]})
    rows.append({"category": "", "code": "", "name": "TOTAL ASET", "amount": data["total_assets"]})
    
    rows.append({"category": "LIABILITIES", "code": "", "name": "--- KEWAJIBAN LANCAR ---", "amount": ""})
    for a in data["current_liabilities"]:
        rows.append({"category": "Current Liability", "code": a.get("code", ""), "name": a.get("name", ""), "amount": a.get("amount", 0)})
    rows.append({"category": "", "code": "", "name": "TOTAL KEWAJIBAN", "amount": data["total_liabilities"]})
    
    rows.append({"category": "EQUITY", "code": "", "name": "--- EKUITAS ---", "amount": ""})
    for a in data["equity"]:
        rows.append({"category": "Equity", "code": a.get("code", ""), "name": a.get("name", ""), "amount": a.get("amount", 0)})
    rows.append({"category": "", "code": "", "name": "TOTAL EKUITAS", "amount": data["total_equity"]})
    rows.append({"category": "", "code": "", "name": "TOTAL KEWAJIBAN & EKUITAS", "amount": data["total_liabilities_and_equity"]})
    
    csv_text = to_csv(rows, ["category", "code", "name", "amount"])
    return FastResponse(content=csv_text, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=balance_sheet_{data['as_of_date']}.csv"})


@api.get("/reports/export/trial_balance")
async def export_trial_balance_csv(as_of_date: str = "", user: dict = Depends(require_module("reports"))):
    data = await report_trial_balance(as_of_date)
    rows = []
    for r in data["rows"]:
        rows.append({"code": r["code"], "name": r["name"], "type": r["account_type"], "debit": r["debit"], "credit": r["credit"]})
    rows.append({"code": "", "name": "TOTAL", "type": "", "debit": data["total_debit"], "credit": data["total_credit"]})
    csv_text = to_csv(rows, ["code", "name", "type", "debit", "credit"])
    return FastResponse(content=csv_text, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=trial_balance_{data['as_of_date']}.csv"})


@api.get("/reports/profit_breakdown", dependencies=[Depends(require_module("reports"))])
async def profit_breakdown(start: str = "", end: str = ""):
    query = {}
    if start: query["date"] = {"$gte": start}
    if end: query.setdefault("date", {})["$lte"] = end
    sales = await db.sales_orders.find(query, {"_id": 0}).to_list(10000)
    by_channel = {}; by_design = {}
    for sale in sales:
        channel = sale.get("sales_channel", "Other")
        channel_row = by_channel.setdefault(channel, {"orders": 0, "revenue": 0, "profit": 0})
        channel_row["orders"] += 1; channel_row["revenue"] += float(sale.get("total", 0)); channel_row["profit"] += float(sale.get("net_profit", 0))
        for item in sale.get("items", []):
            design = item.get("design_name") or item.get("product_name") or item.get("variant_sku", "Unknown")
            design_row = by_design.setdefault(design, {"quantity": 0, "revenue": 0, "profit": 0})
            quantity = float(item.get("quantity", 0)); price = float(item.get("selling_price", 0)); cost = float(item.get("cost", 0))
            design_row["quantity"] += quantity; design_row["revenue"] += quantity * price; design_row["profit"] += quantity * (price - cost)
    return {"by_channel": [{"channel": key, **value} for key, value in by_channel.items()], "by_design": [{"design": key, **value} for key, value in by_design.items()]}


# ---------- AUDIT LOG ----------
@api.get("/audit_logs", dependencies=[Depends(require_role("owner"))])
async def list_audit(limit: int = 200):
    rows = await db.audit_logs.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return json_safe(rows)

# ---------- SEED ----------
async def seed_all():
    # indexes
    await db.users.create_index("email", unique=True)
    await db.products.create_index("sku")
    await db.materials.create_index("name")

    # owner user
    admin_email = os.environ.get("OWNER_EMAIL", DEFAULT_OWNER_EMAIL).lower()
    admin_password = os.environ.get("OWNER_PASSWORD", DEFAULT_OWNER_PASSWORD)
    admin_name = os.environ.get("OWNER_NAME", "NexaBiz Owner")
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

    if DEMO_MODE:
        for email, pwd, name, role in [
            ("admin@example.com", "admin123", "Admin Staff", "admin"),
            ("production@example.com", "production123", "Production Staff", "production"),
            ("finance@example.com", "finance123", "Finance Staff", "finance"),
        ]:
            if not await db.users.find_one({"email": email}):
                await db.users.insert_one({
                    "id": new_id(), "email": email, "password_hash": hash_password(pwd),
                    "name": name, "role": role, "created_at": now_iso(),
                })

    await ensure_coa_seeded()
    cash_acc = await db.accounts.find_one({"code": "1-10001"}) or await db.accounts.find_one({"name": "Kas Tunai"})
    cash_id = cash_acc["id"] if cash_acc else None

    await db.marketplaces.update_one({"name": "TikTok Shop"}, {"$set": {
        "admin_fee_pct": 8, "service_fee_pct": 4, "payment_fee_pct": 0,
        "handling_fee": 1250, "commission_cap": 650000, "return_fee_cap": 5000,
    }})

    # Only seed demo data once
    if await db.products.count_documents({}) > 0:
        return

    logger.info("Seeding demo data...")

    # marketplaces
    await db.marketplaces.insert_many([
        {"id": new_id(), "name": "Shopee", "admin_fee_pct": 4.25, "service_fee_pct": 4.5, "payment_fee_pct": 1.5, "advertising_fee_pct": 0, "created_at": now_iso()},
        {"id": new_id(), "name": "TikTok Shop", "admin_fee_pct": 8, "service_fee_pct": 4, "payment_fee_pct": 0, "handling_fee": 1250, "logistics_fee": 0, "commission_cap": 650000, "return_fee_cap": 5000, "advertising_fee_pct": 0, "created_at": now_iso()},
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
        {"id": mat_sticker, "name": "Packaging Sticker", "unit": "pcs", "stock": 500, "cost": 1500, "minimum_stock": 50, "supplier_id": sup_pack, "created_at": now_iso()},
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
        {"id": new_id(), "sku": "NB-BASIC", "name": "Basic T-Shirt", "category_id": cat_shirt, "brand": "NexaBiz Demo", "material": "Cotton Combed 30s", "image_url": "https://images.pexels.com/photos/8532616/pexels-photo-8532616.jpeg",
         "cost": 54500, "selling_price": 89000, "minimum_stock": 3, "status": "active",
         "variants": variants("RDB", ["Black","White"], ["S","M","L","XL"], 54500, 89000, [8,12,10,5, 6,8,7,4])},
        {"id": new_id(), "sku": "NB-CUSTOM", "name": "Custom T-Shirt", "category_id": cat_shirt, "brand": "NexaBiz Demo", "material": "Cotton Combed 30s", "image_url": "https://images.pexels.com/photos/12025472/pexels-photo-12025472.jpeg",
         "cost": 54500, "selling_price": 109000, "minimum_stock": 3, "status": "active",
         "variants": variants("RDC", ["Black","White"], ["S","M","L","XL"], 54500, 109000, [4,6,5,3, 3,5,4,2])},
        {"id": new_id(), "sku": "NB-TOTE", "name": "Canvas Tote", "category_id": cat_bag, "brand": "NexaBiz Demo", "material": "Canvas",  "image_url": "https://images.unsplash.com/photo-1544816155-12df9643f363",
         "cost": 42000, "selling_price": 79000, "minimum_stock": 3, "status": "active",
         "variants": variants("RDT", ["Natural"], ["OS"], 42000, 79000, [15])},
        {"id": new_id(), "sku": "NB-CAP", "name": "Snapback Cap", "category_id": cat_cap, "brand": "NexaBiz Demo", "material": "Twill",
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
        {"material_id": mat_sticker, "material_name": "Packaging Sticker", "quantity": 1},
        {"material_id": mat_tag, "material_name": "Hang Tag", "quantity": 1},
        {"material_id": mat_card, "material_name": "Thank You Card", "quantity": 1},
    ]
    await db.boms.insert_one({
        "id": new_id(), "product_id": products[0]["id"], "product_name": products[0]["name"],
        "items": bom_items, "created_at": now_iso(),
    })

    # Owner initial capital
    if cash_id:
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
    if cash_id:
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
    try:
        await ensure_coa_seeded()
    except Exception as e:
        logger.exception(f"Error initializing COA: {e}")
    if os.environ.get("SKIP_DEMO_SEED", "").lower() in ("1", "true", "yes") or not DEMO_MODE:
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
    return {"app": "NexaBiz ERP", "status": "ok"}

app.include_router(api)
