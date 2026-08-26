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

    def test_audit_values_are_json_safe(self):
        value = server.json_safe({"id": ObjectId("507f1f77bcf86cd799439011")})
        self.assertEqual(value["id"], "507f1f77bcf86cd799439011")


if __name__ == "__main__":
    unittest.main()