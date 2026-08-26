import os
import unittest
from bson import ObjectId

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "rdcloth_test")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ["USE_MOCK_DB"] = "true"

from fastapi import HTTPException

from backend import server


class BusinessInvariantTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        for collection in ("products", "materials", "production_orders", "sales_orders"):
            await server.db[collection].delete_many({})
        self.user = {"id": "test-user", "email": "test@example.com", "role": "owner"}

    async def test_sales_failure_does_not_partially_reduce_stock(self):
        await server.db.products.insert_one({
            "id": "product-1",
            "name": "Test Product",
            "variants": [{"sku": "SKU-1", "stock": 2, "cost": 10}],
        })

        with self.assertRaises(HTTPException):
            await server.create_sales({
                "items": [
                    {"product_id": "product-1", "variant_sku": "SKU-1", "quantity": 1, "selling_price": 20},
                    {"product_id": "product-1", "variant_sku": "MISSING", "quantity": 1, "selling_price": 20},
                ],
            }, self.user)

        product = await server.db.products.find_one({"id": "product-1"})
        self.assertEqual(product["variants"][0]["stock"], 2)
        self.assertEqual(await server.db.sales_orders.count_documents({}), 0)

    async def test_production_failure_does_not_consume_insufficient_material(self):
        await server.db.materials.insert_one({"id": "material-1", "stock": 1, "cost": 5})
        await server.db.products.insert_one({
            "id": "product-1",
            "variants": [{"sku": "SKU-1", "stock": 0, "cost": 10}],
        })
        await server.db.production_orders.insert_one({
            "id": "production-1",
            "prod_number": "PROD-1",
            "status": "planned",
            "quantity": 2,
            "product_id": "product-1",
            "variant_sku": "SKU-1",
            "bom_items": [{"material_id": "material-1", "quantity": 1}],
        })

        with self.assertRaises(HTTPException):
            await server.complete_production("production-1", {
                "quantity_passed": 2,
                "quantity_rejected": 0,
            }, self.user)

        material = await server.db.materials.find_one({"id": "material-1"})
        product = await server.db.products.find_one({"id": "product-1"})
        self.assertEqual(material["stock"], 1)
        self.assertEqual(product["variants"][0]["stock"], 0)

    async def test_stock_opname_records_delta_and_updates_stock(self):
        await server.db.materials.insert_one({"id": "material-1", "stock": 10, "cost": 5})
        result = await server.stock_opname(server.StockOpnameIn(kind="material", item_id="material-1", physical_stock=7, notes="Counted"), self.user)
        self.assertEqual(result["delta"], -3)
        material = await server.db.materials.find_one({"id": "material-1"})
        self.assertEqual(material["stock"], 7)
        movement = await server.db.inventory_movements.find_one({"ref_type": "opname"})
        self.assertEqual(movement["quantity"], -3)

    async def test_soft_deleted_records_are_hidden_from_active_list(self):
        await server.db.suppliers.insert_one({"id": "supplier-1", "name": "Old Supplier", "status": "active"})
        await server.db.suppliers.update_one({"id": "supplier-1"}, {"$set": {"status": "archived"}})
        active = await server.db.suppliers.find({"status": {"$ne": "archived"}}).to_list(10)
        self.assertEqual(active, [])

    def test_audit_values_are_json_safe(self):
        value = server.json_safe({"id": ObjectId("507f1f77bcf86cd799439011")})
        self.assertEqual(value["id"], "507f1f77bcf86cd799439011")

    async def test_core_business_flow(self):
        await server.db.accounts.insert_one({"id": "account-1", "name": "Kas", "balance": 0, "is_default": True})
        await server.db.materials.insert_one({"id": "material-1", "name": "Kain", "stock": 10, "cost": 5})
        await server.db.products.insert_one({
            "id": "product-1", "name": "Kaos", "variants": [{"sku": "SKU-1", "stock": 0, "cost": 10, "selling_price": 30}],
        })

        po = await server.create_po({
            "supplier_id": "supplier-1", "items": [{"material_id": "material-1", "quantity": 2, "unit_cost": 6}],
            "payment_status": "paid",
        }, self.user)
        await server.receive_po(po["id"], self.user)
        material = await server.db.materials.find_one({"id": "material-1"})
        self.assertEqual(material["stock"], 12)

        production = await server.create_prod({
            "product_id": "product-1", "variant_sku": "SKU-1", "quantity": 2,
            "bom_items": [{"material_id": "material-1", "quantity": 1}],
        }, self.user)
        await server.complete_production(production["id"], {"quantity_passed": 2, "quantity_rejected": 0}, self.user)

        sale = await server.create_sales({
            "order_number": "SO-FLOW-1", "items": [{"product_id": "product-1", "variant_sku": "SKU-1", "quantity": 1, "selling_price": 30}],
            "payment_status": "paid",
        }, self.user)
        product = await server.db.products.find_one({"id": "product-1"})
        self.assertEqual(product["variants"][0]["stock"], 1)
        await server.cancel_sale(sale["id"], self.user)
        product = await server.db.products.find_one({"id": "product-1"})
        self.assertEqual(product["variants"][0]["stock"], 2)
        cancelled = await server.db.sales_orders.find_one({"id": sale["id"]})
        self.assertEqual(cancelled["fulfillment_status"], "cancelled")


if __name__ == "__main__":
    unittest.main()