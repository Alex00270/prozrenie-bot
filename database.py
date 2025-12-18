import os
import asyncpg
import logging
import sys

class Database:
    def __init__(self):
        self.pool = None
        self.db_url = os.getenv("DATABASE_URL")
        
    async def connect(self):
        if not self.pool:
            try:
                self.pool = await asyncpg.create_pool(self.db_url)
                print("DEBUG DB. Connection pool created", flush=True)
            except Exception as e:
                print(f"DEBUG DB.ERROR: {e}", flush=True)
                sys.exit(1)

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

    async def close(self):
        if self.pool: await self.pool.close()

db = Database()
