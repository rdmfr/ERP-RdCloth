import os
import unittest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "nexabiz_test")
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-chars-long-here")
os.environ["USE_MOCK_DB"] = "true"

from fastapi import HTTPException
from backend import server


class AccountingCoaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        for collection in ("accounts", "journal_entries", "financial_transactions", "sales_orders", "expenses", "settings_kv"):
            await server.db[collection].delete_many({})
        self.user = {"id": "test-owner", "email": "owner@example.com", "role": "owner"}
        await server.ensure_coa_seeded()

    async def test_coa_seeding_and_ordering(self):
        accounts = await server.db.accounts.find({"status": {"$ne": "archived"}}, {"_id": 0}).sort([("code", 1), ("created_at", 1)]).to_list(1000)
        self.assertGreaterEqual(len(accounts), 15)
        
        codes = [a.get("code") for a in accounts if a.get("code")]
        self.assertIn("1-10001", codes) # Kas Tunai
        self.assertIn("1-10100", codes) # Piutang Usaha
        self.assertIn("2-10100", codes) # Hutang Usaha
        self.assertIn("3-10000", codes) # Modal Pemilik
        self.assertIn("3-10001", codes) # Ekuitas Saldo Awal
        self.assertIn("4-10000", codes) # Pendapatan Penjualan
        self.assertIn("5-10000", codes) # Beban Pokok Penjualan
        self.assertIn("6-10001", codes) # Beban Iklan

    async def test_opening_balance_workflow(self):
        # 1. Get initial opening balance structure
        initial = await server.get_opening_balance()
        self.assertIn("accounts", initial)
        self.assertTrue("is_balanced" in initial)
        
        accounts = initial["accounts"]
        kas_acc = next((a for a in accounts if a["code"] == "1-10001"), accounts[0])
        bank_acc = next((a for a in accounts if a["code"] == "1-10002"), accounts[1])
        modal_acc = next((a for a in accounts if a["code"] == "3-10000"), accounts[2])
        
        # 2. Save opening balance
        body = server.OpeningBalanceIn(
            as_of_date="2026-01-01",
            auto_balance=True,
            lines=[
                server.OpeningBalanceLine(account_id=kas_acc["id"], debit=10000000, credit=0),
                server.OpeningBalanceLine(account_id=bank_acc["id"], debit=15000000, credit=0),
                server.OpeningBalanceLine(account_id=modal_acc["id"], debit=0, credit=25000000),
            ]
        )
        saved = await server.save_opening_balance(body, self.user)
        self.assertTrue(saved["ok"])
        self.assertEqual(saved["total"], 25000000)
        
        # Check account balance updated
        updated_kas = await server.db.accounts.find_one({"id": kas_acc["id"]})
        self.assertEqual(float(updated_kas["balance"]), 10000000)
        
        # Check journal entry created
        journal = await server.db.journal_entries.find_one({"source_type": "opening_balance"})
        self.assertIsNotNone(journal)
        self.assertEqual(float(journal["total"]), 25000000)

    async def test_balance_sheet_and_trial_balance(self):
        # Seed opening balance
        kas_acc = await server.db.accounts.find_one({"code": "1-10001"})
        modal_acc = await server.db.accounts.find_one({"code": "3-10000"})
        
        body = server.OpeningBalanceIn(
            as_of_date="2026-01-01",
            auto_balance=True,
            lines=[
                server.OpeningBalanceLine(account_id=kas_acc["id"], debit=50000000, credit=0),
                server.OpeningBalanceLine(account_id=modal_acc["id"], debit=0, credit=50000000),
            ]
        )
        await server.save_opening_balance(body, self.user)
        
        # 1. Test Trial Balance
        tb = await server.report_trial_balance("2026-01-01")
        self.assertTrue(tb["is_balanced"])
        self.assertGreaterEqual(tb["total_debit"], 50000000)
        self.assertEqual(tb["total_debit"], tb["total_credit"])
        
        # 2. Test Balance Sheet
        bs = await server.report_balance_sheet("2026-01-01")
        self.assertTrue(bs["is_balanced"])
        self.assertGreaterEqual(bs["total_assets"], 50000000)
        self.assertEqual(bs["total_assets"], bs["total_liabilities_and_equity"])
        
        # 3. Test General Ledger
        gl = await server.report_general_ledger(kas_acc["id"])
        self.assertIn("transactions", gl)
        self.assertGreaterEqual(len(gl["transactions"]), 1)
        self.assertEqual(gl["ending_balance"], 50000000)
