import os
import asyncpg
import logging
import sys
from motor.motor_asyncio import AsyncIOMotorClient # Нужно добавить в requirements.txt

class Database:
    def __init__(self):
        self.pool = None
        self.mongo_client = None
        self.mongo_db = None
        
        # Берем оба URL
        self.pg_url = os.getenv("DATABASE_URL")
        self.mongo_uri = os.getenv("MONGO_URI")

        # HOTFIX ДЛЯ RENDER/POSTGRES
        if self.pg_url and self.pg_url.startswith("postgresql+asyncpg://"):
            self.pg_url = self.pg_url.replace("postgresql+asyncpg://", "postgresql://")

    async def connect(self):
        # 1. ПОДКЛЮЧЕНИЕ К POSTGRES (для старых ботов)
        if not self.pool and self.pg_url:
            print(f"DEBUG DB. Connecting to Postgres...", flush=True)
            try:
                self.pool = await asyncpg.create_pool(self.pg_url)
                print("DEBUG DB. Postgres pool created", flush=True)
            except Exception as e:
                print(f"DEBUG DB. Postgres ERROR: {e}", flush=True)

        # 2. ПОДКЛЮЧЕНИЕ К MONGO (специально для Незабудки)
        if not self.mongo_client and self.mongo_uri:
            print(f"DEBUG DB. Connecting to MongoDB...", flush=True)
            try:
                self.mongo_client = AsyncIOMotorClient(self.mongo_uri)
                # Из твоего скриншота Render: база называется nezabudka_ai
                self.mongo_db = self.mongo_client["nezabudka_ai"]
                print("DEBUG DB. MongoDB connected", flush=True)
            except Exception as e:
                print(f"DEBUG DB. MongoDB ERROR: {e}", flush=True)

    # Метод для старых ботов (Postgres)
    async def add_user(self, telegram_id: int, username: str, full_name: str, bot_id: int):
        if not self.pool: await self.connect()
        try:
            async with self.pool.acquire() as connection:
                await connection.execute("""
                    INSERT INTO users (telegram_id, username, full_name, bot_id)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (telegram_id, bot_id) DO NOTHING
                """, telegram_id, username, full_name, bot_id)
        except Exception as e:
            print(f"DEBUG DB. Insert failed: {e}", flush=True)

    # НОВЫЙ МЕТОД ДЛЯ НЕЗАБУДКИ (MongoDB)
    async def add_task(self, task_data: dict):
        if not self.mongo_db: await self.connect()
        try:
            result = await self.mongo_db.tasks.insert_one(task_data)
            return result.inserted_id
        except Exception as e:
            print(f"DEBUG DB. Mongo Insert failed: {e}", flush=True)
            return None

    async def close(self):
        if self.pool: await self.pool.close()
        if self.mongo_client: self.mongo_client.close()

db = Database()
