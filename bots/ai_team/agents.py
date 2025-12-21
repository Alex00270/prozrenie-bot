import os
import httpx
import logging

async def call_agent(role, prompt, previous_context=""):
    """
    Возвращает: (текст_ответа, реальное_имя_модели)
    """
    current_dir = os.path.dirname(__file__)
    profile_path = os.path.join(current_dir, "profiles", f"{role}.txt")
    
    system_instruction = "Ты полезный ассистент."
    if os.path.exists(profile_path):
        with open(profile_path, "r", encoding="utf-8") as f:
            system_instruction = f.read()

    # СБОРКА КОНТЕКСТА
    if previous_context:
        full_user_content = (
            f"=== КОНТЕКСТ И МНЕНИЯ КОЛЛЕГ ===\n{previous_context}\n"
            f"================================\n\nТВОЯ ЗАДАЧА:\n{prompt}"
        )
    else:
        full_user_content = prompt

    gateway_url = os.getenv("GATEWAY_BASE_URL")
    api_key = os.getenv("GATEWAY_API_KEY")
    
    # ВОТ ТУТ ГИБКОСТЬ:
    # Бот берет модель из Render. Если там пусто — просит "auto".
    requested_model = os.getenv("MODEL_NAME", "auto")

    if not gateway_url:
        return "❌ Ошибка: Нет GATEWAY_BASE_URL", "System"

    payload = {
        "model": requested_model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": full_user_content}
        ]
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(
                f"{gateway_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload
            )
            
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                # ФАКТ: Какая модель реально сгенерировала это
                real_model = data.get("model", requested_model)
                return content, real_model
            else:
                return f"⚠️ Ошибка шлюза: {resp.status_code}", "Error"
                
        except Exception as e:
            return f"⚠️ Ошибка сети: {str(e)}", "Network"
