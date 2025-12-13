from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, Text, DateTime, func, select
import os
import datetime

# Получаем URL базы. Если нет — используем временную SQLite (но данные пропадут при деплое!)
DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///local.db")

engine = create_async_engine(DB_URL, echo=False)
new_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# --- ТАБЛИЦА ЛИДОВ ---
class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    username: Mapped[str] = mapped_column(Text, nullable=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Ответы пользователя
    audience: Mapped[str] = mapped_column(Text, nullable=True)
    pain: Mapped[str] = mapped_column(Text, nullable=True)
    competitors: Mapped[str] = mapped_column(Text, nullable=True)
    magic: Mapped[str] = mapped_column(Text, nullable=True)
    grandma: Mapped[str] = mapped_column(Text, nullable=True)
    goal: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Результат от AI
    ai_diagnosis: Mapped[str] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

# --- ФУНКЦИИ ---
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def add_lead(user_id, username, full_name, answers, ai_result):
    async with new_session() as session:
        lead = Lead(
            user_id=user_id,
            username=username,
            full_name=full_name,
            audience=answers.get('a1'),
            pain=answers.get('a2'),
            competitors=answers.get('a3'),
            magic=answers.get('a4'),
            grandma=answers.get('a5'),
            goal=answers.get('a6'),
            ai_diagnosis=ai_result
        )
        session.add(lead)
        await session.commit()

async def get_stats():
    async with new_session() as session:
        result = await session.execute(select(func.count(Lead.id)))
        count = result.scalar()
        return count

async def get_all_leads():
    async with new_session() as session:
        result = await session.execute(select(Lead).order_by(Lead.created_at.desc()))
        return result.scalars().all()
