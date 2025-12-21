# database.py
import os
import asyncio
import asyncpg
from motor.motor_asyncio import AsyncIOMotorClient


class Database:
    def __init__(self):
        self.pool = None
        self.mongo_client = None
        self.mongo_db = None

        self.pg_url = os.getenv("DATABASE_URL")
        self.mongo_uri = os.getenv("MONGO_URI")

        print("DB INIT ----------------", flush=True)
        print("Postgres URL:", bool(self.pg_url), flush=True)
        print("Mongo URI:", bool(self.mongo_uri), flush=True)

    async def connect_mongo(self):
        if self.mongo_client or not self.mongo_uri:
            return

        try:
            print("DB: connecting to MongoDB...", flush=True)
            self.mongo_client = AsyncIOMotorClient(
                self.mongo_uri,
                serverSelectionTimeoutMS=3000,
                connectTimeoutMS=3000,
                tlsAllowInvalidCertificates=True,
            )
            self.mongo_db = self.mongo_client["nezabudka_ai"]
            print("DB: MongoDB client created", flush=True)

        except Exception as e:
            print("DB: Mongo init ERROR:", e, flush=True)

    async def add_task(self, task_data: dict):
        print("DB: add_task() called", flush=True)

        # ❗️ Коннектим Mongo ЯВНО и ОДИН раз
        if self.mongo_db is None:
            await self.connect_mongo()

        if self.mongo_db is None:
            print("DB: Mongo unavailable, skipping insert", flush=True)
            return None

        try:
            # ❗️ КЛЮЧЕВО: таймаут, чтобы UX не умирал
            result = await asyncio.wait_for(
                self.mongo_db.tasks.insert_one(task_data),
                timeout=3
            )
            print("DB: task inserted:", result.inserted_id, flush=True)
            return result.inserted_id

        except asyncio.TimeoutError:
            print("DB: Mongo INSERT TIMEOUT", flush=True)

        except Exception as e:
            print("DB: Mongo INSERT ERROR:", e, flush=True)

        return None


db = Database()
