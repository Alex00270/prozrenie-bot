import os
import httpx
import logging

async def call_agent(role, prompt):
    # Строим путь: папка бота / profiles / role.txt
    # Render запускает код из корня, поэтому путь относительный
    current_dir = os.path.dirname(__file__)
    profile_path = os.path.join(current_dir, "profiles", f"{role}.txt")
    
    system_instruction = "Ты полезный ассистент."
    
    # Читаем твои файлы
    if os.path.exists(profile_path):
        with open(profile_path, "r", encoding="utf-8") as f:
            system_instruction = f.read()
    else:
        logging.warning(f"⚠️ Профиль {role} не найден по пути {profile_path}")

    # Данные из Render
    gateway_url = os.getenv("GATEWAY_BASE_URL")
    api_key = os.getenv("GATEWAY_API_KEY")
    
    if not gateway_url:
        return "❌ Ошибка: Нет GATEWAY_BASE_URL в настройках."

    payload = {
        "model": "gemini-2.0-flash-exp", # Или "gpt-4o"
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
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
                return resp.json()["choices"][0]["message"]["content"]
            else:
                return f"Ошибка шлюза: {resp.status_code}"
        except Exception as e:
            return f"Ошибка сети: {str(e)}"
