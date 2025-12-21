from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from utils.ai_engine import ask_brain, safe_reply

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("👋 Привет! Я HR-ассистент и помощник по офису. Чем помочь?")

@router.message()
async def handle_staff(message: Message):
    msg = await message.answer("📁 Поднимаю документы...")
    
    sys_prompt = "Ты полезный и вежливый офисный помощник. Отвечай четко и по делу."
    
    text, model, src = await ask_brain(sys_prompt, message.text)
    
    await msg.delete()
    await safe_reply(message, "📄 **Ответ:**", text, f"{model} | {src}")
