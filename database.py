# database.py
import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient


class Database:
    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI")
        self.mongo_db_name = "nezabudka_prod"

        self.mongo_client = None
        self.mongo_db = None

        print("DB INIT =====================", flush=True)
        print("Mongo URI exists:", bool(self.mongo_uri), flush=True)
        print("Mongo DB name:", self.mongo_db_name, flush=True)

    async def connect(self):
        if self.mongo_db is not None:
            return

        if not self.mongo_uri:
            print("⛔ MONGO_URI is NOT set", flush=True)
            return

        try:
            print("DB: connecting to MongoDB...", flush=True)

            self.mongo_client = AsyncIOMotorClient(
                self.mongo_uri,
                serverSelectionTimeoutMS=3000,
                connectTimeoutMS=3000,
                tlsAllowInvalidCertificates=True,
            )

            # ВАЖНО: НЕ делаем await здесь — motor ленивый
            self.mongo_db = self.mongo_client[self.mongo_db_name]

            print("DB: MongoDB client created", flush=True)

        except Exception as e:
            print("⛔ Mongo init error:", e, flush=True)

    async def add_task(self, task_doc: dict):
        print("DB: add_task() called", flush=True)

        if self.mongo_db is None:
            await self.connect()

        if self.mongo_db is None:
            print("⛔ Mongo unavailable — task NOT saved", flush=True)
            return None

        try:
            result = await asyncio.wait_for(
                self.mongo_db.tasks.insert_one(task_doc),
                timeout=3
            )
            print("✅ Task saved:", result.inserted_id, flush=True)
            return result.inserted_id

        except asyncio.TimeoutError:
            print("⛔ Mongo INSERT TIMEOUT", flush=True)

        except Exception as e:
            print("⛔ Mongo INSERT ERROR:", e, flush=True)

        return None


db = Database()
