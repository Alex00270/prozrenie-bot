import os
import asyncio
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

class Database:
    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI")
        # ВАЖНО: Имя базы берем как на Dallas
        self.mongo_db_name = "nezabudka_ai" 
        self.mongo_client = None
        self.mongo_db = None

    async def connect(self):
        if self.mongo_db is not None: return
        if not self.mongo_uri:
            print("⛔ MONGO_URI is NOT set", flush=True)
            return
        try:
            self.mongo_client = AsyncIOMotorClient(
                self.mongo_uri,
                serverSelectionTimeoutMS=3000,
                tlsAllowInvalidCertificates=True,
            )
            self.mongo_db = self.mongo_client[self.mongo_db_name]
            print(f"DB: Connected to {self.mongo_db_name}", flush=True)
        except Exception as e:
            print(f"⛔ Mongo init error: {e}", flush=True)

    # --- USER TRACKING (Analytics) ---
    async def track_activity(self, user):
        """Записываем активность юзера (как в боте на Dallas)"""
        if self.mongo_db is None: await self.connect()
        if self.mongo_db is None or user is None: return

        try:
            doc = {
                'username': user.username,
                'first_name': user.first_name,
                'last_active_at': datetime.utcnow()
            }
            # Upsert: обновляем или создаем
            await self.mongo_db.users.update_one(
                {'_id': user.id},
                {'$set': doc, '$setOnInsert': {'joined_at': datetime.utcnow()}, '$inc': {'interaction_count': 1}},
                upsert=True
            )
        except Exception as e:
            print(f"Analytics Error: {e}", flush=True)

    # --- TASKS ---
    async def add_task(self, task_doc: dict):
        if self.mongo_db is None: await self.connect()
        try:
            if "status" not in task_doc: task_doc["status"] = "pending"
            res = await self.mongo_db.tasks.insert_one(task_doc)
            return res.inserted_id
        except Exception: return None

    async def get_active_tasks(self, user_id: int, limit=50):
        if self.mongo_db is None: await self.connect()
        try:
            # Сортировка: Сначала новые (как в Dallas: DESCENDING)
            # Но для списка удобнее старые сверху? В Dallas было list, потом reverse.
            # Сделаем created_at DESC (новые сверху)
            cursor = self.mongo_db.tasks.find(
                {"user_id": user_id, "status": "pending"}
            ).sort("created_at", -1).limit(limit)
            
            tasks = await cursor.to_list(length=limit)
            return tasks # Возвращаем как есть (самые свежие первыми)
        except Exception: return []

    async def mark_done_by_index(self, user_id: int, index: int):
        """
        Находит N-ю задачу в списке активных и помечает DONE.
        Index 1-based (1, 2, 3...)
        """
        tasks = await self.get_active_tasks(user_id, limit=50)
        # В Dallas список переворачивался (tasks.reverse()), значит 1 - это самая старая?
        # Или самая новая? Обычно 1 - это то, что сверху.
        # Давайте считать 1 = самая верхняя в выводе /list.
        
        if index < 1 or index > len(tasks):
            return None
        
        # Берем задачу
        target_task = tasks[index - 1] 
        task_id = target_task['_id']
        
        await self.mongo_db.tasks.update_one(
            {'_id': task_id},
            {'$set': {'status': 'done'}}
        )
        return target_task.get('action', 'Задача')

    # --- STATS ---
    async def get_global_stats(self):
        if self.mongo_db is None: await self.connect()
        if self.mongo_db is None: return {}
        try:
            now = datetime.utcnow()
            day_ago = now - timedelta(days=1)
            week_ago = now - timedelta(days=7)

            # Users
            u_total = await self.mongo_db.users.count_documents({})
            u_24h = await self.mongo_db.users.count_documents({"last_active_at": {"$gte": day_ago}})
            u_7d = await self.mongo_db.users.count_documents({"last_active_at": {"$gte": week_ago}})

            # Tasks
            t_total = await self.mongo_db.tasks.count_documents({})
            t_pending = await self.mongo_db.tasks.count_documents({"status": "pending"})

            return {
                "u_total": u_total, "u_24h": u_24h, "u_7d": u_7d,
                "t_total": t_total, "t_pending": t_pending
            }
        except Exception: return {}

db = Database()
