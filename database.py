# database.py
import os
import asyncpg
from motor.motor_asyncio import AsyncIOMotorClient

class Database:
    def __init__(self):
        self.pool = None
        self.mongo_client = None
        self.mongo_db = None
        self.pg_url = os.getenv("DATABASE_URL")
        self.mongo_uri = os.getenv("MONGO_URI")

    async def connect(self):
        # Postgres... (без изменений)
        if not self.pool and self.pg_url:
            self.pool = await asyncpg.create_pool(self.pg_url)

        # Mongo SSL fix
        if self.mongo_client is None and self.mongo_uri:
            try:
                self.mongo_client = AsyncIOMotorClient(
                    self.mongo_uri, 
                    tlsAllowInvalidCertificates=True,
                    connectTimeoutMS=30000,
                    serverSelectionTimeoutMS=30000
                )
                self.mongo_db = self.mongo_client["nezabudka_ai"]
                print("DEBUG DB. MongoDB connected", flush=True)
            except Exception as e:
                print(f"DEBUG DB. MongoDB ERROR: {e}", flush=True)

    async def add_task(self, task_data: dict):
        # В MongoDB нельзя использовать 'if not db', только явное сравнение с None
        if self.mongo_db is None: 
            await self.connect()
        
        try:
            if self.mongo_db is not None:
                result = await self.mongo_db.tasks.insert_one(task_data)
                return result.inserted_id
        except Exception as e:
            print(f"DEBUG DB. Mongo Insert failed: {e}", flush=True)
            return None

db = Database()
