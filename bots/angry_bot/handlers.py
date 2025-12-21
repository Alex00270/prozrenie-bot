from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from utils.ai_engine import ask_brain, safe_reply

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("🤨 Я Скептик. Пиши идею, я найду в ней дыры.")

@router.message()
async def handle_roast(message: Message):
    msg = await message.answer("🔥 Ищу недостатки...")
    
    sys_prompt = "Ты злой, циничный критик. Унижай идею пользователя фактами и сарказмом. Будь краток."
    
    text, model, src = await ask_brain(sys_prompt, message.text)
    
    await msg.delete()
    await safe_reply(message, "💀 **Вердикт:**", text, f"{model} | {src}")
