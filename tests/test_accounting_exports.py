import os
import unittest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "nexabiz_test")
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-chars-long-here")
os.environ["USE_MOCK_DB"] = "true"

from fastapi import HTTPException
from backend import server


class AccountingExportsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await server.init_db()
        for collection in ("products", "materials", "customers", "suppliers", "sales_orders", "purchase_orders", "accounts", "journal_entries", "expenses", "settings_kv"):
            await server.db[collection].delete_many({})
        self.user = {"id": "test-owner", "email": "owner@example.com", "role": "owner"}
        await server.ensure_coa_seeded()
        
        # Seed basic transaction and order data
        prod_id = server.new_id()
        await server.db.products.insert_one({
            "id": prod_id, "name": "Kaos Export Demo", "category_id": "Kaos", "cost": 40000, "selling_price": 85000, "minimum_stock": 5, "status": "active",
            "variants": [{"sku": "EXP-TSHIRT-L", "color": "Hitam", "size": "L", "cost": 40000, "selling_price": 85000, "stock": 25}],
        })
        
        await server.db.materials.insert_one({
            "id": server.new_id(), "name": "Kain Katun Murni", "sku": "RAW-KTN-01", "category": "Kain", "unit": "kg", "cost": 100000, "stock": 10, "minimum_stock": 2, "status": "active",
        })
        
        await server.db.sales_orders.insert_one({
            "id": server.new_id(), "order_number": "SO-EXP-001", "date": "2026-09-01T10:00:00Z", "customer_name": "Buyer Export", "sales_channel": "Shopee",
            "items": [{"product_id": prod_id, "product_name": "Kaos Export Demo", "variant_sku": "EXP-TSHIRT-L", "quantity": 2, "selling_price": 85000, "cost": 40000}],
            "subtotal": 170000, "discount": 0, "shipping": 10000, "marketplace_fee": 15000, "advertising_cost": 5000, "cogs": 80000, "total": 180000, "net_profit": 80000,
            "payment_status": "paid", "fulfillment_status": "completed",
        })
        
        await server.db.purchase_orders.insert_one({
            "id": server.new_id(), "po_number": "PO-EXP-001", "order_date": "2026-08-25T10:00:00Z", "supplier_name": "Vendor Tekstil",
            "total_amount": 1000000, "paid_amount": 1000000, "payment_status": "paid", "received_status": "received",
        })

    async def test_csv_exports(self):
        # 1. Profit & Loss CSV
        resp_pl = await server.export_profit_loss_csv("", "", self.user)
        self.assertEqual(resp_pl.media_type, "text/csv")
        content_pl = resp_pl.body.decode()
        self.assertIn("Pendapatan Penjualan (Gross Revenue)", content_pl)
        self.assertIn("LABA KOTOR (GROSS PROFIT)", content_pl)

        # 2. Balance Sheet CSV
        resp_bs = await server.export_balance_sheet_csv("", self.user)
        self.assertEqual(resp_bs.media_type, "text/csv")
        content_bs = resp_bs.body.decode()
        self.assertIn("ASET", content_bs)

        # 3. Trial Balance CSV
        resp_tb = await server.export_trial_balance_csv("", self.user)
        self.assertEqual(resp_tb.media_type, "text/csv")

        # 4. General Ledger CSV
        resp_gl = await server.export_general_ledger_csv("", "", "", self.user)
        self.assertEqual(resp_gl.media_type, "text/csv")

        # 5. Journals CSV
        resp_jn = await server.export_journals_csv("", "", self.user)
        self.assertEqual(resp_jn.media_type, "text/csv")

        # 6. Sales CSV
        resp_sl = await server.export_sales_csv("", "", self.user)
        self.assertEqual(resp_sl.media_type, "text/csv")
        self.assertIn("SO-EXP-001", resp_sl.body.decode())

        # 7. Inventory Valuation CSV
        resp_iv = await server.export_inventory_valuation_csv(self.user)
        self.assertEqual(resp_iv.media_type, "text/csv")
        content_iv = resp_iv.body.decode()
        self.assertIn("EXP-TSHIRT-L", content_iv)
        self.assertIn("RAW-KTN-01", content_iv)

        # 8. Purchases CSV
        resp_po = await server.export_purchases_csv("", "", self.user)
        self.assertEqual(resp_po.media_type, "text/csv")
        self.assertIn("PO-EXP-001", resp_po.body.decode())

    async def test_pdf_exports(self):
        # 1. Profit & Loss PDF
        pdf_pl = await server.export_profit_loss_pdf("", "", self.user)
        self.assertEqual(pdf_pl.media_type, "application/pdf")
        body_pl = b"".join([chunk async for chunk in pdf_pl.body_iterator])
        self.assertTrue(body_pl.startswith(b"%PDF-"))

        # 2. Balance Sheet PDF
        pdf_bs = await server.export_balance_sheet_pdf("", self.user)
        self.assertEqual(pdf_bs.media_type, "application/pdf")
        body_bs = b"".join([chunk async for chunk in pdf_bs.body_iterator])
        self.assertTrue(body_bs.startswith(b"%PDF-"))

        # 3. Trial Balance PDF
        pdf_tb = await server.export_trial_balance_pdf("", self.user)
        self.assertEqual(pdf_tb.media_type, "application/pdf")
        body_tb = b"".join([chunk async for chunk in pdf_tb.body_iterator])
        self.assertTrue(body_tb.startswith(b"%PDF-"))

        # 4. General Ledger PDF
        acc = await server.db.accounts.find_one({"code": "1-10001"})
        pdf_gl = await server.export_general_ledger_pdf(acc["id"], "", "", self.user)
        self.assertEqual(pdf_gl.media_type, "application/pdf")
        body_gl = b"".join([chunk async for chunk in pdf_gl.body_iterator])
        self.assertTrue(body_gl.startswith(b"%PDF-"))
