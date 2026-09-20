import os
import unittest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "nexabiz_test")
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-chars-long-here")
os.environ["USE_MOCK_DB"] = "true"

from fastapi import HTTPException
from backend import server


class ImportWizardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        for collection in ("products", "materials", "customers", "suppliers", "sales_orders", "accounts", "journal_entries", "inventory_movements", "audit_logs"):
            await server.db[collection].delete_many({})
        self.user = {"id": "test-admin", "email": "admin@example.com", "role": "owner"}
        await server.ensure_coa_seeded()

    async def test_template_download(self):
        # 1. Product template
        resp_prod = await server.get_import_template("products")
        self.assertEqual(resp_prod.media_type, "text/csv")
        self.assertIn("name,sku,category,selling_price,cost,stock,color,size,min_stock", resp_prod.body.decode())

        # 2. Material template
        resp_mat = await server.get_import_template("materials")
        self.assertIn("name,sku,category,unit,cost,stock,min_stock", resp_mat.body.decode())

        # 3. Opening balance template
        resp_ob = await server.get_import_template("opening_balance")
        self.assertIn("account_code,debit,credit", resp_ob.body.decode())

    async def test_product_preview_validation(self):
        rows = [
            {"name": "Kaos Polos Premium", "sku": "KP-PREM-BLK-L", "category": "Kaos", "selling_price": 85000, "cost": 45000, "stock": 50, "color": "Hitam", "size": "L"},
            {"name": "", "sku": "KP-INVALID", "selling_price": 85000, "cost": 45000, "stock": 50}, # missing name
            {"name": "Kaos Minus Price", "sku": "KP-MINUS", "selling_price": -1000, "cost": 45000, "stock": 10}, # negative price
            {"name": "Kaos Dupe SKU", "sku": "KP-PREM-BLK-L", "selling_price": 85000, "cost": 45000, "stock": 10}, # dupe sku in batch
        ]
        
        preview = await server.preview_import(server.ImportPreviewIn(kind="products", rows=rows), self.user)
        self.assertEqual(preview["total"], 4)
        self.assertEqual(preview["valid_count"], 1)
        self.assertEqual(preview["invalid_count"], 3)
        self.assertFalse(preview["is_all_valid"])

        # Row 1 valid
        self.assertTrue(preview["rows"][0]["is_valid"])
        # Row 2 invalid (missing name)
        self.assertFalse(preview["rows"][1]["is_valid"])
        self.assertIn("Nama produk wajib diisi.", preview["rows"][1]["errors"])
        # Row 3 invalid (negative price)
        self.assertFalse(preview["rows"][2]["is_valid"])
        self.assertIn("Harga jual tidak boleh negatif.", preview["rows"][2]["errors"])
        # Row 4 invalid (duplicate sku in batch)
        self.assertFalse(preview["rows"][3]["is_valid"])
        self.assertIn("duplikat dalam file import ini", preview["rows"][3]["errors"][0])

    async def test_strict_mode_atomic_rollback(self):
        # In strict mode (allow_partial=False), if any row fails, NOTHING should be imported
        rows = [
            {"name": "Valid Product 1", "sku": "VP-01", "selling_price": 100000, "cost": 50000, "stock": 20},
            {"name": "Invalid Product 2", "sku": "", "selling_price": 100000, "cost": 50000, "stock": 20}, # missing sku
        ]
        
        with self.assertRaises(HTTPException) as ctx:
            await server.execute_import(server.ImportExecuteIn(kind="products", rows=rows, allow_partial=False), self.user)
        
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Import dibatalkan (Strict Mode)", ctx.exception.detail)
        
        # Verify no product was inserted
        count = await server.db.products.count_documents({})
        self.assertEqual(count, 0)

    async def test_successful_product_and_material_import(self):
        prod_rows = [
            {"name": "Hoodie Fleece Basic", "sku": "HOD-BLK-M", "category": "Outerwear", "selling_price": 175000, "cost": 95000, "stock": 15, "color": "Black", "size": "M"},
            {"name": "Hoodie Fleece Basic", "sku": "HOD-BLK-L", "category": "Outerwear", "selling_price": 175000, "cost": 95000, "stock": 20, "color": "Black", "size": "L"},
        ]
        
        exec_prod = await server.execute_import(server.ImportExecuteIn(kind="products", rows=prod_rows, allow_partial=True), self.user)
        self.assertTrue(exec_prod["ok"])
        
        # Verify product created with 2 variants
        prod = await server.db.products.find_one({"name": "Hoodie Fleece Basic"})
        self.assertIsNotNone(prod)
        self.assertEqual(len(prod["variants"]), 2)
        self.assertEqual(prod["variants"][0]["sku"], "HOD-BLK-M")
        self.assertEqual(prod["variants"][1]["sku"], "HOD-BLK-L")

        # Material import
        mat_rows = [
            {"name": "Kain Fleece Katun Hitam", "sku": "RAW-FLC-BLK", "category": "Kain", "unit": "kg", "cost": 135000, "stock": 40.5, "min_stock": 10},
            {"name": "Tali Hoodie Hitam", "sku": "RAW-TLI-BLK", "category": "Aksesoris", "unit": "meter", "cost": 2500, "stock": 200, "min_stock": 20},
        ]
        exec_mat = await server.execute_import(server.ImportExecuteIn(kind="materials", rows=mat_rows, allow_partial=True), self.user)
        self.assertTrue(exec_mat["ok"])
        self.assertEqual(exec_mat["created"], 2)

        mat = await server.db.materials.find_one({"sku": "RAW-FLC-BLK"})
        self.assertIsNotNone(mat)
        self.assertEqual(mat["stock"], 40.5)

    async def test_sales_order_import_and_stock_deduction(self):
        # 1. Setup product
        await server.execute_import(server.ImportExecuteIn(kind="products", rows=[
            {"name": "T-Shirt Oversized", "sku": "TS-OVR-BLK-L", "selling_price": 120000, "cost": 60000, "stock": 10},
        ]), self.user)
        
        # 2. Import sales order
        so_rows = [
            {
                "order_number": "SO-TEST-001",
                "date": "2026-09-01",
                "customer_name": "Budi Marketplace",
                "sales_channel": "Shopee",
                "variant_sku": "TS-OVR-BLK-L",
                "quantity": 3,
                "selling_price": 120000,
                "discount": 10000,
                "shipping": 15000,
                "marketplace_fee": 12000,
                "advertising_cost": 5000,
            }
        ]
        exec_so = await server.execute_import(server.ImportExecuteIn(kind="sales_orders", rows=so_rows), self.user)
        self.assertTrue(exec_so["ok"])
        self.assertEqual(exec_so["created"], 1)

        # 3. Check order created and stock deducted from 10 to 7
        order = await server.db.sales_orders.find_one({"order_number": "SO-TEST-001"})
        self.assertIsNotNone(order)
        self.assertEqual(order["total"], (120000 * 3) - 10000 + 15000)
        self.assertEqual(order["payment_status"], "paid")

        prod = await server.db.products.find_one({"variants.sku": "TS-OVR-BLK-L"})
        v = next(x for x in prod["variants"] if x["sku"] == "TS-OVR-BLK-L")
        self.assertEqual(v["stock"], 7)

    async def test_opening_balance_import(self):
        ob_rows = [
            {"account_code": "1-10001", "debit": 20000000, "credit": 0}, # Kas Tunai
            {"account_code": "1-10002", "debit": 30000000, "credit": 0}, # Bank BCA
            {"account_code": "2-10100", "debit": 0, "credit": 10000000}, # Hutang Usaha
        ]
        exec_ob = await server.execute_import(server.ImportExecuteIn(kind="opening_balance", rows=ob_rows), self.user)
        self.assertTrue(exec_ob["ok"])
        self.assertEqual(exec_ob["created"], 3)

        kas = await server.db.accounts.find_one({"code": "1-10001"})
        self.assertEqual(kas["balance"], 20000000)

        # Check journal entry created
        journals = await server.db.journal_entries.find({"source_type": "opening_balance"}).to_list(10)
        self.assertGreater(len(journals), 0)
