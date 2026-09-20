import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / "backend" / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt

def hash_pwd(pwd):
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()

async def main():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "rdcloth")
    print(f"Connecting to {db_name}...")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    users = await db.users.find({}).to_list(10)
    print(f"Existing users in DB ({len(users)}):")
    for u in users:
        print(f" - {u.get('email')} (role: {u.get('role')})")
        
    owner_email = os.environ.get("OWNER_EMAIL", "rddev@gmail.com").lower()
    owner_pwd = os.environ.get("OWNER_PASSWORD", "rdcloth2026")
    
    # Ensure owner exists
    existing_owner = await db.users.find_one({"email": owner_email})
    if not existing_owner:
        await db.users.insert_one({
            "id": "owner-main",
            "email": owner_email,
            "name": "NexaBiz Owner",
            "role": "owner",
            "status": "active",
            "password_hash": hash_pwd(owner_pwd),
        })
        print(f"Created owner account: {owner_email} / {owner_pwd}")
    else:
        await db.users.update_one({"email": owner_email}, {"$set": {"password_hash": hash_pwd(owner_pwd), "status": "active"}})
        print(f"Updated password for owner: {owner_email} / {owner_pwd}")

    # Ensure demo accounts exist
    demos = [
        ("admin@example.com", "admin123", "Admin Staff", "admin"),
        ("production@example.com", "production123", "Production Staff", "production"),
        ("finance@example.com", "finance123", "Finance Staff", "finance"),
    ]
    for email, pwd, name, role in demos:
        u = await db.users.find_one({"email": email})
        if not u:
            await db.users.insert_one({
                "id": f"{role}-demo",
                "email": email,
                "name": name,
                "role": role,
                "status": "active",
                "password_hash": hash_pwd(pwd),
            })
            print(f"Created demo account: {email} / {pwd}")
        else:
            await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_pwd(pwd), "status": "active"}})
            print(f"Updated demo account: {email} / {pwd}")

    # Clear any rate limits/lockouts
    await db.login_attempts.delete_many({})
    print("Cleared all login lockouts.")

if __name__ == "__main__":
    asyncio.run(main())
