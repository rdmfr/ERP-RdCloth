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
        for collection in ("products", "materials", "production_orders", "sales_orders", "suppliers", "customers", "accounts", "marketplaces", "expense_categories", "financial_transactions", "inventory_movements"):
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

    async def test_seeded_finance_accounts_include_requested_accounts(self):
        await server.db.accounts.delete_many({})
        await server.seed_all()
        names = {doc["name"] for doc in await server.db.accounts.find({}, {"_id": 0, "name": 1}).to_list(100)}
        for required in ["Kas Tunai", "Bank BCA", "Blu by BCA Digital", "SeaBank", "BRI", "E-Wallet DANA", "GoPay", "Hutang"]:
            self.assertIn(required, names)

    async def test_dtf_costing_includes_reject_and_design_expense(self):
        result = await server.calculate_dtf_costing({
            "design_name": "Vibe Graphite",
            "quantity": 20,
            "blank_cost": 30000,
            "dtf_transfer_cost": 15000,
            "printing_cost": 5000,
            "labor_cost": 3000,
            "packaging_cost": 2000,
            "design_setup_cost": 50000,
            "reject_rate": 0.1,
            "selling_price": 95000,
        }, self.user)

        self.assertEqual(result["reject_qty"], 2)
        self.assertGreater(result["unit_cost"], 0)
        self.assertGreater(result["suggested_price"], result["unit_cost"])
        self.assertEqual(result["design_name"], "Vibe Graphite")

    async def test_paid_purchase_deducts_selected_finance_account(self):
        await server.db.accounts.insert_many([
            {"id": "cash-account", "name": "Kas Tunai", "balance": 100000, "is_default": True},
            {"id": "bca-account", "name": "Bank BCA", "balance": 500000},
        ])
        await server.db.materials.insert_one({"id": "shirt-blank", "name": "Kaos Polos", "stock": 0, "cost": 30000})

        po = await server.create_po({
            "supplier_id": "supplier-1",
            "account_id": "bca-account",
            "items": [{"material_id": "shirt-blank", "quantity": 2, "unit_cost": 30000}],
            "payment_status": "paid",
        }, self.user)
        await server.receive_po(po["id"], self.user)

        account = await server.db.accounts.find_one({"id": "bca-account"})
        cash_account = await server.db.accounts.find_one({"id": "cash-account"})
        self.assertEqual(account["balance"], 440000)
        self.assertEqual(cash_account["balance"], 100000)
        transaction = await server.db.financial_transactions.find_one({"ref_type": "purchase_order", "ref_id": po["id"]})
        self.assertEqual(transaction["account_id"], "bca-account")
        self.assertEqual(transaction["amount"], 60000)

    async def test_shopee_fee_uses_price_after_store_discount(self):
        await server.db.accounts.insert_one({"id": "sales-account", "name": "Bank BCA", "balance": 0, "is_default": True})
        await server.db.marketplaces.insert_one({
            "id": "shopee", "name": "Shopee", "admin_fee_pct": 4.25,
            "service_fee_pct": 4.5, "payment_fee_pct": 1.5,
        })
        await server.db.products.insert_one({
            "id": "shopee-product", "name": "Kaos Shopee",
            "variants": [{"sku": "SHOPEE-M", "stock": 1, "cost": 30000}],
        })

        sale = await server.create_sales({
            "sales_channel": "Shopee",
            "discount": 10000,
            "items": [{"product_id": "shopee-product", "variant_sku": "SHOPEE-M", "quantity": 1, "selling_price": 150000}],
        }, self.user)

        self.assertEqual(sale["marketplace_fee_base"], 140000)
        self.assertEqual(sale["marketplace_fee"], 14350)

    async def test_tiktok_shop_adds_commission_handling_and_return_allowance(self):
        await server.db.accounts.insert_one({"id": "tiktok-account", "name": "Bank BCA", "balance": 0, "is_default": True})
        await server.db.marketplaces.insert_one({
            "id": "tiktok", "name": "TikTok Shop", "admin_fee_pct": 8,
            "service_fee_pct": 4, "payment_fee_pct": 0, "handling_fee": 1250,
            "logistics_fee": 260, "commission_cap": 650000, "return_fee_cap": 5000,
        })
        await server.db.products.insert_one({
            "id": "tiktok-product", "name": "Kaos TikTok",
            "variants": [{"sku": "TIKTOK-M", "stock": 1, "cost": 30000}],
        })

        sale = await server.create_sales({
            "sales_channel": "TikTok Shop", "return_rate_pct": 50,
            "items": [{"product_id": "tiktok-product", "variant_sku": "TIKTOK-M", "quantity": 1, "selling_price": 100000}],
        }, self.user)

        self.assertEqual(sale["marketplace_fee"], 12000)
        self.assertEqual(sale["handling_fee"], 1250)
        self.assertEqual(sale["logistics_fee"], 260)
        self.assertEqual(sale["return_allowance"], 2500)

    async def test_marketplace_settlement_credits_account_once(self):
        await server.db.accounts.insert_one({"id": "settle-account", "name": "Bank BCA", "balance": 100000, "is_default": True})
        await server.db.marketplaces.insert_one({"id": "shopee", "name": "Shopee", "admin_fee_pct": 10})
        await server.db.products.insert_one({"id": "settle-product", "name": "Kaos", "variants": [{"sku": "SETTLE-M", "stock": 1, "cost": 30000}]})
        sale = await server.create_sales({"sales_channel": "Shopee", "items": [{"product_id": "settle-product", "variant_sku": "SETTLE-M", "quantity": 1, "selling_price": 100000}]}, self.user)
        self.assertEqual(await server.db.financial_transactions.count_documents({"ref_type": "sales_order"}), 0)
        settlement = await server.create_settlement({"order_ids": [sale["id"]], "account_id": "settle-account"}, self.user)
        self.assertEqual(settlement["net_amount"], 90000)
        self.assertEqual((await server.db.accounts.find_one({"id": "settle-account"}))["balance"], 190000)

    async def test_good_return_restores_stock_and_records_refund(self):
        await server.db.accounts.insert_one({"id": "return-account", "name": "Kas", "balance": 0, "is_default": True})
        await server.db.products.insert_one({"id": "return-product", "name": "Kaos", "variants": [{"sku": "RETURN-M", "stock": 1, "cost": 30000}]})
        sale = await server.create_sales({"sales_channel": "Direct/Offline", "items": [{"product_id": "return-product", "variant_sku": "RETURN-M", "quantity": 1, "selling_price": 50000}]}, self.user)
        await server.create_return({"sales_order_id": sale["id"], "variant_sku": "RETURN-M", "quantity": 1, "condition": "good", "refund_amount": 50000}, self.user)
        product = await server.db.products.find_one({"id": "return-product"})
        self.assertEqual(product["variants"][0]["stock"], 1)
        self.assertEqual(await server.db.financial_transactions.count_documents({"ref_type": "return"}), 1)

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