import logging
import uuid
from typing import Any, Dict, List, Optional, Union
from sqlalchemy import String, select, update, delete, func, or_, and_, asc, desc, text
try:
    import models
    from database import AsyncSessionLocal, init_db
except ImportError:
    from backend import models
    from backend.database import AsyncSessionLocal, init_db

logger = logging.getLogger("rdcloth.pg_db")

TABLE_MODEL_MAP = {
    "users": models.User,
    "login_attempts": models.LoginAttempt,
    "audit_logs": models.AuditLog,
    "settings_kv": models.SettingsKV,
    "attachments": models.Attachment,
    "categories": models.Category,
    "products": models.Product,
    "materials": models.Material,
    "suppliers": models.Supplier,
    "customers": models.Customer,
    "inventory_movements": models.InventoryMovement,
    "sales_orders": models.SalesOrder,
    "invoices": models.Invoice,
    "returns": models.Return,
    "purchase_orders": models.PurchaseOrder,
    "bills": models.Bill,
    "boms": models.BOM,
    "production_orders": models.ProductionOrder,
    "accounts": models.Account,
    "journal_entries": models.JournalEntry,
    "financial_transactions": models.FinancialTransaction,
    "expenses": models.Expense,
    "expense_categories": models.ExpenseCategory,
    "assets": models.Asset,
    "reconciliations": models.Reconciliation,
    "marketplaces": models.Marketplace,
    "marketplace_settlements": models.MarketplaceSettlement,
    "crm_activities": models.CRMActivity,
}

class InsertResult:
    def __init__(self, inserted_id: Any):
        self.inserted_id = inserted_id

class UpdateResult:
    def __init__(self, modified_count: int):
        self.modified_count = modified_count

class DeleteResult:
    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count

class PGCursor:
    def __init__(self, collection: "PGCollection", filter_dict: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None):
        self.collection = collection
        self.filter_dict = filter_dict or {}
        self.projection = projection or {}
        self._sort_clauses = []
        self._skip = 0
        self._limit = None

    def sort(self, field_or_list: Union[str, List[tuple]], direction: int = 1) -> "PGCursor":
        if isinstance(field_or_list, list):
            for field, d in field_or_list:
                self._add_sort(field, d)
        elif isinstance(field_or_list, str):
            self._add_sort(field_or_list, direction)
        return self

    def _add_sort(self, field: str, direction: int):
        model_cls = self.collection.model_cls
        if hasattr(model_cls, field):
            col = getattr(model_cls, field)
            self._sort_clauses.append(desc(col) if direction in (-1, "desc", "DESC") else asc(col))

    def skip(self, count: int) -> "PGCursor":
        self._skip = count
        return self

    def limit(self, count: int) -> "PGCursor":
        self._limit = count
        return self

    async def to_list(self, length: Optional[int] = None) -> List[Dict[str, Any]]:
        limit = length if length is not None else self._limit
        return await self.collection._execute_find(
            self.filter_dict,
            projection=self.projection,
            sort_clauses=self._sort_clauses,
            skip=self._skip,
            limit=limit,
        )

    def __aiter__(self):
        self._items = None
        self._idx = 0
        return self

    async def __anext__(self):
        if self._items is None:
            self._items = await self.to_list(self._limit)
        if self._idx < len(self._items):
            item = self._items[self._idx]
            self._idx += 1
            return item
        raise StopAsyncIteration


class PGCollection:
    def __init__(self, name: str, session_getter):
        self.name = name
        self.model_cls = TABLE_MODEL_MAP.get(name)
        self._session_getter = session_getter

    def _build_where(self, filter_dict: Dict[str, Any]):
        clauses = []
        model = self.model_cls

        for key, val in filter_dict.items():
            if key == "$or" and isinstance(val, list):
                or_clauses = []
                for sub_filter in val:
                    sub_where = self._build_where(sub_filter)
                    if sub_where:
                        or_clauses.append(and_(*sub_where))
                if or_clauses:
                    clauses.append(or_(*or_clauses))
                continue

            if key == "_id":
                key = "id"

            if "." in key:
                col_name, sub_path = key.split(".", 1)
                if hasattr(model, col_name):
                    col = getattr(model, col_name)
                    clauses.append(col.cast(String).contains(f'"{val}"'))
                continue

            if not hasattr(model, key):
                if hasattr(model, "extra_data"):
                    extra_value = model.extra_data[key].as_string()
                    if isinstance(val, dict):
                        for op, op_val in val.items():
                            if op == "$ne":
                                clauses.append(or_(extra_value != str(op_val), extra_value.is_(None)))
                            elif op == "$in":
                                clauses.append(extra_value.in_([str(item) for item in op_val]))
                            elif op == "$regex":
                                clauses.append(extra_value.ilike(f"%{op_val}%"))
                    else:
                        clauses.append(extra_value == str(val))
                continue

            col = getattr(model, key)

            if isinstance(val, dict):
                for op, op_val in val.items():
                    if op == "$ne":
                        clauses.append(or_(col != op_val, col.is_(None)))
                    elif op == "$in":
                        clauses.append(col.in_(op_val))
                    elif op == "$gte":
                        clauses.append(col >= op_val)
                    elif op == "$lte":
                        clauses.append(col <= op_val)
                    elif op == "$gt":
                        clauses.append(col > op_val)
                    elif op == "$lt":
                        clauses.append(col < op_val)
                    elif op == "$regex":
                        clauses.append(col.ilike(f"%{op_val}%"))
            else:
                clauses.append(col == val)

        return clauses

    async def find_one(self, filter_dict: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        results = await self._execute_find(filter_dict or {}, projection=projection, limit=1)
        return results[0] if results else None

    def find(self, filter_dict: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None) -> PGCursor:
        return PGCursor(self, filter_dict=filter_dict, projection=projection)

    async def _execute_find(
        self,
        filter_dict: Dict[str, Any],
        projection: Optional[Dict[str, Any]] = None,
        sort_clauses: Optional[List[Any]] = None,
        skip: int = 0,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        async with self._session_getter() as session:
            stmt = select(self.model_cls)
            where_clauses = self._build_where(filter_dict)
            if where_clauses:
                stmt = stmt.where(*where_clauses)
            if sort_clauses:
                stmt = stmt.order_by(*sort_clauses)
            if skip > 0:
                stmt = stmt.offset(skip)
            if limit is not None:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            instances = result.scalars().all()

            out = []
            for inst in instances:
                if hasattr(inst, "to_dict"):
                    d = inst.to_dict(include_hash=True)
                else:
                    d = {c.name: getattr(inst, c.name) for c in inst.__table__.columns}

                # Handle projection if specified (e.g. {"_id": 0, "password_hash": 0})
                if projection:
                    for p_key, p_val in projection.items():
                        if p_val == 0 or p_val is False:
                            d.pop(p_key, None)
                out.append(d)
            return out

    async def insert_one(self, doc: Dict[str, Any]) -> InsertResult:
        doc = dict(doc)
        doc.pop("_id", None)
        if "id" not in doc or not doc["id"]:
            doc["id"] = doc.get("key") or doc.get("code") or str(uuid.uuid4())
        if self.name == "materials" and not doc.get("name"):
            doc["name"] = doc.get("code") or doc["id"]
        if self.name == "products" and not doc.get("name"):
            doc["name"] = doc.get("sku") or doc["id"]
        if hasattr(self.model_cls, "key") and "key" not in doc and "id" in doc:
            doc["key"] = doc["id"]

        valid_cols = {c.name for c in self.model_cls.__table__.columns}
        model_kwargs = {k: v for k, v in doc.items() if k in valid_cols}
        extra = {k: v for k, v in doc.items() if k not in valid_cols}
        if extra and hasattr(self.model_cls, "extra_data"):
            model_kwargs["extra_data"] = extra

        async with self._session_getter() as session:
            instance = self.model_cls(**model_kwargs)
            session.add(instance)
            await session.commit()
            return InsertResult(instance.id if hasattr(instance, "id") else None)

    async def insert_many(self, docs: List[Dict[str, Any]]):
        if not docs:
            return
        valid_cols = {c.name for c in self.model_cls.__table__.columns}
        instances = []
        for doc in docs:
            d = dict(doc)
            d.pop("_id", None)
            if "id" not in d or not d["id"]:
                d["id"] = d.get("key") or d.get("code") or str(uuid.uuid4())
            if hasattr(self.model_cls, "key") and "key" not in d and "id" in d:
                d["key"] = d["id"]
            kwargs = {k: v for k, v in d.items() if k in valid_cols}
            extra = {k: v for k, v in d.items() if k not in valid_cols}
            if extra and hasattr(self.model_cls, "extra_data"):
                kwargs["extra_data"] = extra
            instances.append(self.model_cls(**kwargs))

        async with self._session_getter() as session:
            session.add_all(instances)
            await session.commit()

    async def update_one(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any], upsert: bool = False) -> UpdateResult:
        where_clauses = self._build_where(filter_dict)
        async with self._session_getter() as session:
            instance = None
            if where_clauses:
                stmt = select(self.model_cls).where(*where_clauses).limit(1)
                result = await session.execute(stmt)
                instance = result.scalar_one_or_none()

            if not instance:
                if upsert:
                    doc = dict(filter_dict)
                    if "$set" in update_dict:
                        doc.update(update_dict["$set"])
                    for k, v in update_dict.items():
                        if not k.startswith("$"):
                            doc[k] = v
                    await self.insert_one(doc)
                    return UpdateResult(1)
                return UpdateResult(0)

            if "$set" in update_dict:
                for k, v in update_dict["$set"].items():
                    if hasattr(instance, k):
                        setattr(instance, k, v)
                    elif hasattr(instance, "extra_data"):
                        ed = dict(instance.extra_data or {})
                        ed[k] = v
                        instance.extra_data = ed

            if "$inc" in update_dict:
                for k, v in update_dict["$inc"].items():
                    if hasattr(instance, k):
                        cur = getattr(instance, k) or 0
                        setattr(instance, k, cur + v)

            # direct set without $set
            for k, v in update_dict.items():
                if not k.startswith("$"):
                    if hasattr(instance, k):
                        setattr(instance, k, v)
                    elif hasattr(instance, "extra_data"):
                        ed = dict(instance.extra_data or {})
                        ed[k] = v
                        instance.extra_data = ed

            await session.commit()
            return UpdateResult(1)

    async def update_many(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any], upsert: bool = False) -> UpdateResult:
        where_clauses = self._build_where(filter_dict)
        async with self._session_getter() as session:
            instances = []
            if where_clauses:
                stmt = select(self.model_cls).where(*where_clauses)
                result = await session.execute(stmt)
                instances = result.scalars().all()

            if not instances:
                if upsert:
                    doc = dict(filter_dict)
                    if "$set" in update_dict:
                        doc.update(update_dict["$set"])
                    for k, v in update_dict.items():
                        if not k.startswith("$"):
                            doc[k] = v
                    await self.insert_one(doc)
                    return UpdateResult(1)
                return UpdateResult(0)

        async with self._session_getter() as session:
            stmt = select(self.model_cls).where(*where_clauses)
            result = await session.execute(stmt)
            instances = result.scalars().all()
            count = 0
            for instance in instances:
                if "$set" in update_dict:
                    for k, v in update_dict["$set"].items():
                        if hasattr(instance, k):
                            setattr(instance, k, v)
                if "$inc" in update_dict:
                    for k, v in update_dict["$inc"].items():
                        if hasattr(instance, k):
                            cur = getattr(instance, k) or 0
                            setattr(instance, k, cur + v)
                count += 1
            await session.commit()
            return UpdateResult(count)

    async def delete_one(self, filter_dict: Dict[str, Any]) -> DeleteResult:
        where_clauses = self._build_where(filter_dict)
        if not where_clauses:
            return DeleteResult(0)

        async with self._session_getter() as session:
            stmt = select(self.model_cls).where(*where_clauses).limit(1)
            res = await session.execute(stmt)
            inst = res.scalar_one_or_none()
            if inst:
                await session.delete(inst)
                await session.commit()
                return DeleteResult(1)
            return DeleteResult(0)

    async def delete_many(self, filter_dict: Dict[str, Any]) -> DeleteResult:
        where_clauses = self._build_where(filter_dict)
        async with self._session_getter() as session:
            stmt = delete(self.model_cls)
            if where_clauses:
                stmt = stmt.where(*where_clauses)
            res = await session.execute(stmt)
            await session.commit()
            return DeleteResult(res.rowcount or 0)

    async def count_documents(self, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        where_clauses = self._build_where(filter_dict or {})
        async with self._session_getter() as session:
            stmt = select(func.count()).select_from(self.model_cls)
            if where_clauses:
                stmt = stmt.where(*where_clauses)
            res = await session.execute(stmt)
            return res.scalar() or 0

    async def create_index(self, *args, **kwargs):
        # Indexes are defined on models in PostgreSQL schema
        return True


class PGDatabase:
    def __init__(self, session_factory=AsyncSessionLocal):
        self.session_factory = session_factory
        self._collections = {}

    def __getattr__(self, name: str) -> PGCollection:
        if name not in self._collections:
            self._collections[name] = PGCollection(name, self.session_factory)
        return self._collections[name]

    def __getitem__(self, name: str) -> PGCollection:
        return getattr(self, name)
