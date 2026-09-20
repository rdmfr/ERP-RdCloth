from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import String, Text, Float, Integer, Boolean, JSON, Column
from sqlalchemy.dialects.postgresql import JSONB
try:
    from database import Base
except ImportError:
    from backend.database import Base

def json_type():
    return JSON().with_variant(JSONB, "postgresql")

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class BaseModelMixin:
    extra_data = Column(json_type(), default=dict)

    def to_dict(self, include_hash: bool = False) -> Dict[str, Any]:
        data = {c.name: getattr(self, c.name) for c in self.__table__.columns if c.name not in ("extra_data", "password_hash")}
        if self.extra_data and isinstance(self.extra_data, dict):
            for k, v in self.extra_data.items():
                if k not in data:
                    data[k] = v
        if include_hash and hasattr(self, "password_hash"):
            data["password_hash"] = self.password_hash
        return data


# ---------- 1. AUTH & AUDIT ----------
class User(Base, BaseModelMixin):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="admin")
    status = Column(String(50), default="active")
    created_at = Column(String(50), default=now_iso)
    updated_at = Column(String(50), default=now_iso)


class LoginAttempt(Base, BaseModelMixin):
    __tablename__ = "login_attempts"

    id = Column(String(64), primary_key=True)
    email = Column(String(255), index=True, nullable=True)
    ip = Column(String(100), index=True, nullable=True)
    success = Column(Boolean, default=False)
    timestamp = Column(String(50), default=now_iso, index=True)


class AuditLog(Base, BaseModelMixin):
    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), index=True, nullable=True)
    user_email = Column(String(255), nullable=True)
    action = Column(String(100), nullable=True, index=True)
    entity = Column(String(100), index=True, nullable=True)
    entity_id = Column(String(64), index=True, nullable=True)
    old_value = Column(json_type(), nullable=True)
    new_value = Column(json_type(), nullable=True)
    created_at = Column(String(50), default=now_iso, index=True)


class SettingsKV(Base, BaseModelMixin):
    __tablename__ = "settings_kv"

    id = Column(String(100), primary_key=True)
    key = Column(String(100), index=True, nullable=True)
    value = Column(json_type(), nullable=True)
    updated_at = Column(String(50), default=now_iso)


class Attachment(Base, BaseModelMixin):
    __tablename__ = "attachments"

    id = Column(String(64), primary_key=True)
    entity_type = Column(String(100), index=True)
    entity_id = Column(String(64), index=True)
    original_name = Column(String(255))
    stored_name = Column(String(255))
    content_type = Column(String(100))
    size = Column(Integer, default=0)
    uploaded_by = Column(String(64))
    created_at = Column(String(50), default=now_iso)


# ---------- 2. MASTER DATA & INVENTORY ----------
class Category(Base, BaseModelMixin):
    __tablename__ = "categories"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), index=True, nullable=False)
    kind = Column(String(50), default="product")
    description = Column(Text, nullable=True)
    created_at = Column(String(50), default=now_iso)


class Product(Base, BaseModelMixin):
    __tablename__ = "products"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    sku = Column(String(100), index=True, nullable=True)
    category_id = Column(String(64), index=True, nullable=True)
    brand = Column(String(100), nullable=True)
    material = Column(String(100), nullable=True)
    image_url = Column(Text, nullable=True)
    base_price = Column(Float, default=0.0)
    selling_price = Column(Float, default=0.0)
    cost = Column(Float, default=0.0)
    cost_price = Column(Float, default=0.0)
    minimum_stock = Column(Float, default=0.0)
    description = Column(Text, nullable=True)
    variants = Column(json_type(), default=list)
    images = Column(json_type(), default=list)
    status = Column(String(50), default="active")
    created_at = Column(String(50), default=now_iso)
    updated_at = Column(String(50), default=now_iso)


class Material(Base, BaseModelMixin):
    __tablename__ = "materials"

    id = Column(String(64), primary_key=True)
    code = Column(String(100), index=True, nullable=True)
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(100), nullable=True)
    unit = Column(String(50), default="pcs")
    stock = Column(Float, default=0.0)
    min_stock = Column(Float, default=0.0)
    minimum_stock = Column(Float, default=0.0)
    cost = Column(Float, default=0.0)
    cost_price = Column(Float, default=0.0)
    supplier_id = Column(String(64), nullable=True)
    created_at = Column(String(50), default=now_iso)
    updated_at = Column(String(50), default=now_iso)


class Supplier(Base, BaseModelMixin):
    __tablename__ = "suppliers"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    contact = Column(String(255), nullable=True)
    contact_person = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    lead_time_days = Column(Integer, default=0)
    created_at = Column(String(50), default=now_iso)


class Customer(Base, BaseModelMixin):
    __tablename__ = "customers"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    customer_type = Column(String(50), default="new")
    total_orders = Column(Integer, default=0)
    total_spending = Column(Float, default=0.0)
    created_at = Column(String(50), default=now_iso)


class InventoryMovement(Base, BaseModelMixin):
    __tablename__ = "inventory_movements"

    id = Column(String(64), primary_key=True)
    item_id = Column(String(64), index=True)
    item_type = Column(String(50), default="product")
    type = Column(String(50))
    qty = Column(Float, default=0.0)
    balance_after = Column(Float, default=0.0)
    ref_type = Column(String(100), nullable=True)
    ref_id = Column(String(64), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(String(50), default=now_iso, index=True)


# ---------- 3. ORDERS & TRANSACTIONS ----------
class SalesOrder(Base, BaseModelMixin):
    __tablename__ = "sales_orders"

    id = Column(String(64), primary_key=True)
    order_number = Column(String(100), index=True)
    customer_id = Column(String(64), index=True, nullable=True)
    customer_name = Column(String(255), nullable=True)
    date = Column(String(50), nullable=True)
    sales_channel = Column(String(100), default="direct")
    channel = Column(String(100), default="direct")
    marketplace_id = Column(String(64), nullable=True)
    items = Column(json_type(), default=list)
    subtotal = Column(Float, default=0.0)
    cogs = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    voucher = Column(Float, default=0.0)
    shipping = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    marketplace_fee = Column(Float, default=0.0)
    other_fee = Column(Float, default=0.0)
    advertising_cost = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    total_amount = Column(Float, default=0.0)
    net_profit = Column(Float, default=0.0)
    payment_status = Column(String(50), default="unpaid")
    fulfillment_status = Column(String(50), default="unfulfilled")
    notes = Column(Text, nullable=True)
    created_at = Column(String(50), default=now_iso, index=True)
    updated_at = Column(String(50), default=now_iso)


class Invoice(Base, BaseModelMixin):
    __tablename__ = "invoices"

    id = Column(String(64), primary_key=True)
    invoice_number = Column(String(100), index=True)
    order_id = Column(String(64), index=True, nullable=True)
    customer_id = Column(String(64), index=True, nullable=True)
    amount = Column(Float, default=0.0)
    status = Column(String(50), default="draft")
    due_date = Column(String(50), nullable=True)
    items = Column(json_type(), default=list)
    created_at = Column(String(50), default=now_iso)


class Return(Base, BaseModelMixin):
    __tablename__ = "returns"

    id = Column(String(64), primary_key=True)
    return_number = Column(String(100), index=True)
    order_id = Column(String(64), index=True)
    items = Column(json_type(), default=list)
    reason = Column(Text, nullable=True)
    status = Column(String(50), default="pending")
    refund_amount = Column(Float, default=0.0)
    created_at = Column(String(50), default=now_iso)


class PurchaseOrder(Base, BaseModelMixin):
    __tablename__ = "purchase_orders"

    id = Column(String(64), primary_key=True)
    po_number = Column(String(100), index=True)
    supplier_id = Column(String(64), index=True, nullable=True)
    supplier_name = Column(String(255), nullable=True)
    items = Column(json_type(), default=list)
    total_amount = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    status = Column(String(50), default="draft")
    payment_status = Column(String(50), default="unpaid")
    notes = Column(Text, nullable=True)
    created_at = Column(String(50), default=now_iso, index=True)
    updated_at = Column(String(50), default=now_iso)


class Bill(Base, BaseModelMixin):
    __tablename__ = "bills"

    id = Column(String(64), primary_key=True)
    bill_number = Column(String(100), index=True)
    po_id = Column(String(64), index=True, nullable=True)
    supplier_id = Column(String(64), index=True, nullable=True)
    amount = Column(Float, default=0.0)
    status = Column(String(50), default="unpaid")
    due_date = Column(String(50), nullable=True)
    items = Column(json_type(), default=list)
    created_at = Column(String(50), default=now_iso)


# ---------- 4. MANUFACTURING & PRODUCTION ----------
class BOM(Base, BaseModelMixin):
    __tablename__ = "boms"

    id = Column(String(64), primary_key=True)
    product_id = Column(String(64), index=True)
    product_name = Column(String(255), nullable=True)
    variant_id = Column(String(64), index=True, nullable=True)
    items = Column(json_type(), default=list)
    materials = Column(json_type(), default=list)
    notes = Column(Text, nullable=True)
    created_at = Column(String(50), default=now_iso)


class ProductionOrder(Base, BaseModelMixin):
    __tablename__ = "production_orders"

    id = Column(String(64), primary_key=True)
    prod_number = Column(String(100), index=True)
    product_id = Column(String(64), index=True)
    variant_id = Column(String(64), nullable=True)
    quantity = Column(Float, default=1.0)
    status = Column(String(50), default="pending")
    stage = Column(String(100), default="cutting")
    assigned_to = Column(String(255), nullable=True)
    start_date = Column(String(50), nullable=True)
    due_date = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(String(50), default=now_iso)
    updated_at = Column(String(50), default=now_iso)


# ---------- 5. FINANCE & ACCOUNTING ----------
class Account(Base, BaseModelMixin):
    __tablename__ = "accounts"

    id = Column(String(64), primary_key=True)
    code = Column(String(50), index=True, nullable=True)
    name = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)
    type = Column(String(50), nullable=True)
    kind = Column(String(50), nullable=True)
    account_type = Column(String(50), nullable=True)
    subtype = Column(String(100), nullable=True)
    normal_balance = Column(String(50), nullable=True)
    balance = Column(Float, default=0.0)
    is_default = Column(Boolean, default=False)
    is_system = Column(Boolean, default=False)
    status = Column(String(50), default="active")
    created_at = Column(String(50), default=now_iso)
    updated_at = Column(String(50), default=now_iso)


class JournalEntry(Base, BaseModelMixin):
    __tablename__ = "journal_entries"

    id = Column(String(64), primary_key=True)
    entry_number = Column(String(100), index=True)
    date = Column(String(50), index=True)
    description = Column(Text, nullable=True)
    ref_type = Column(String(100), nullable=True)
    ref_id = Column(String(64), nullable=True)
    lines = Column(json_type(), default=list)
    total_debit = Column(Float, default=0.0)
    total_credit = Column(Float, default=0.0)
    created_at = Column(String(50), default=now_iso)


class FinancialTransaction(Base, BaseModelMixin):
    __tablename__ = "financial_transactions"

    id = Column(String(64), primary_key=True)
    type = Column(String(50))
    amount = Column(Float, default=0.0)
    account_id = Column(String(64), index=True)
    description = Column(Text, nullable=True)
    ref_type = Column(String(100), nullable=True)
    ref_id = Column(String(64), nullable=True)
    date = Column(String(50), default=now_iso, index=True)
    created_at = Column(String(50), default=now_iso)


class Expense(Base, BaseModelMixin):
    __tablename__ = "expenses"

    id = Column(String(64), primary_key=True)
    date = Column(String(50), default=now_iso, index=True)
    category = Column(String(100))
    description = Column(Text, nullable=True)
    amount = Column(Float, default=0.0)
    account_id = Column(String(64), index=True, nullable=True)
    created_at = Column(String(50), default=now_iso)


class ExpenseCategory(Base, BaseModelMixin):
    __tablename__ = "expense_categories"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), index=True)
    description = Column(Text, nullable=True)
    created_at = Column(String(50), default=now_iso)


class Asset(Base, BaseModelMixin):
    __tablename__ = "assets"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    purchase_price = Column(Float, default=0.0)
    purchase_date = Column(String(50))
    useful_life_years = Column(Float, default=5.0)
    residual_value = Column(Float, default=0.0)
    created_at = Column(String(50), default=now_iso)


class Reconciliation(Base, BaseModelMixin):
    __tablename__ = "reconciliations"

    id = Column(String(64), primary_key=True)
    account_id = Column(String(64), index=True)
    statement_date = Column(String(50))
    statement_balance = Column(Float, default=0.0)
    book_balance = Column(Float, default=0.0)
    diff = Column(Float, default=0.0)
    items = Column(json_type(), default=list)
    created_at = Column(String(50), default=now_iso)


# ---------- 6. MARKETPLACE & CRM ----------
class Marketplace(Base, BaseModelMixin):
    __tablename__ = "marketplaces"

    id = Column(String(64), primary_key=True)
    name = Column(String(100), index=True)
    admin_fee_pct = Column(Float, default=0.0)
    service_fee_pct = Column(Float, default=0.0)
    payment_fee_pct = Column(Float, default=0.0)
    handling_fee = Column(Float, default=0.0)
    commission_cap = Column(Float, default=0.0)
    return_fee_cap = Column(Float, default=0.0)
    advertising_fee_pct = Column(Float, default=0.0)
    logistics_fee = Column(Float, default=0.0)
    created_at = Column(String(50), default=now_iso)


class MarketplaceSettlement(Base, BaseModelMixin):
    __tablename__ = "marketplace_settlements"

    id = Column(String(64), primary_key=True)
    marketplace_id = Column(String(64), index=True)
    settlement_date = Column(String(50), index=True)
    net_amount = Column(Float, default=0.0)
    raw_data = Column(json_type(), default=dict)
    created_at = Column(String(50), default=now_iso)


class CRMActivity(Base, BaseModelMixin):
    __tablename__ = "crm_activities"

    id = Column(String(64), primary_key=True)
    customer_id = Column(String(64), index=True)
    type = Column(String(100))
    notes = Column(Text, nullable=True)
    date = Column(String(50), default=now_iso)
    created_at = Column(String(50), default=now_iso)
