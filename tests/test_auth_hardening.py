import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "nexabiz_test")
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-chars-long-here")
os.environ["USE_MOCK_DB"] = "true"

from fastapi import HTTPException
from backend import server


class AuthHardeningTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        for collection in ("users", "login_attempts", "audit_logs"):
            await server.db[collection].delete_many({})
        self.owner = {
            "id": "owner-1",
            "email": "owner@example.com",
            "password_hash": server.hash_password("OwnerPass123"),
            "name": "Super Owner",
            "role": "owner",
            "status": "active",
            "created_at": server.now_iso()
        }
        await server.db.users.insert_one(self.owner)

    def _mock_request(self, ip="192.168.1.10"):
        req = MagicMock()
        req.client.host = ip
        req.headers = {}
        req.url.scheme = "http"
        return req

    def _mock_response(self):
        res = MagicMock()
        res.set_cookie = MagicMock()
        res.delete_cookie = MagicMock()
        return res

    async def test_password_complexity_validation(self):
        # Too short (< 8 chars)
        with self.assertRaises(HTTPException):
            server.validate_password_strength("pass1")
            
        # No numbers
        with self.assertRaises(HTTPException):
            server.validate_password_strength("passwordOnly")
            
        # No letters
        with self.assertRaises(HTTPException):
            server.validate_password_strength("1234567890")
            
        # Valid password
        server.validate_password_strength("StrongPass123")

    async def test_brute_force_lockout(self):
        req = self._mock_request(ip="10.0.0.1")
        res = self._mock_response()
        
        # 5 failed login attempts
        for _ in range(5):
            with self.assertRaises(HTTPException) as cm:
                await server.login(server.LoginIn(email="owner@example.com", password="WrongPassword1"), res, req)
            self.assertEqual(cm.exception.status_code, 401)

        # 6th attempt should trigger 429 Too Many Requests Lockout even with correct password!
        with self.assertRaises(HTTPException) as cm:
            await server.login(server.LoginIn(email="owner@example.com", password="OwnerPass123"), res, req)
        self.assertEqual(cm.exception.status_code, 429)
        self.assertIn("terkunci", cm.exception.detail.lower())

    async def test_inactive_user_cannot_login(self):
        req = self._mock_request(ip="10.0.0.2")
        res = self._mock_response()
        
        # Create an inactive user
        await server.db.users.insert_one({
            "id": "staff-1",
            "email": "staff@example.com",
            "password_hash": server.hash_password("StaffPass123"),
            "name": "Inactive Staff",
            "role": "admin",
            "status": "inactive",
            "created_at": server.now_iso()
        })
        
        with self.assertRaises(HTTPException) as cm:
            await server.login(server.LoginIn(email="staff@example.com", password="StaffPass123"), res, req)
        self.assertEqual(cm.exception.status_code, 403)
        self.assertIn("dinonaktifkan", cm.exception.detail.lower())

    async def test_user_management_lifecycle(self):
        owner_user = {"id": self.owner["id"], "email": self.owner["email"], "role": "owner"}
        
        # 1. Create user
        new_staff = await server.create_user(
            server.UserCreate(email="finance@example.com", password="FinancePass123", name="Staff Finance", role="finance"),
            owner_user
        )
        self.assertEqual(new_staff["email"], "finance@example.com")
        self.assertEqual(new_staff["status"], "active")
        
        # 2. Update user name & status to inactive
        updated = await server.update_user(
            new_staff["id"],
            server.UserUpdate(name="Senior Finance", status="inactive"),
            owner_user
        )
        self.assertEqual(updated["name"], "Senior Finance")
        self.assertEqual(updated["status"], "inactive")
        
        # 3. Reset password by owner
        reset_res = await server.reset_user_password(
            new_staff["id"],
            server.ResetPasswordIn(new_password="NewFinancePass456"),
            owner_user
        )
        self.assertTrue(reset_res["ok"])
        
        # 4. Self change password
        staff_user = {"id": new_staff["id"], "email": "finance@example.com", "role": "finance"}
        change_res = await server.change_password(
            server.ChangePasswordIn(current_password="NewFinancePass456", new_password="MyOwnSecret789"),
            staff_user
        )
        self.assertTrue(change_res["ok"])
