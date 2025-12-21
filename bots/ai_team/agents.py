import os
import httpx
import logging

# Читаем конфиги. Если их нет - падаем с ошибкой сразу, а не потом.
GATEWAY_URL = os.getenv("GATEWAY_BASE_URL", "http://172.86.90.213:3000/v1")
GATEWAY_KEY = os.getenv("GATEWAY_API_KEY", "sk-gateway-alex-2025")

async def call_agent(role, prompt):
    """
    Отправляет запрос агенту через API Gateway в Далласе.
    """
    # 1. Загружаем системный промпт
    # Используем os.path.join для совместимости с любой ОС (Linux/Windows/Mac)
    profile_path = os.path.join(os.getcwd(), "bots", "ai_team", "profiles", f"{role}.txt")
    
    system_instruction = "Ты полезный помощник."
    if os.path.exists(profile_path):
        with open(profile_path, "r", encoding="utf-8") as f:
            system_instruction = f.read()
    else:
        logging.error(f"CRITICAL: Профиль {role} не найден по пути {profile_path}")
        return f"⚠️ Ошибка: Профиль сотрудника '{role}' утерян."

    # 2. Формируем тело запроса (OpenAI-compatible)
    payload = {
        "model": "auto", 
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ]
    }
    
    headers = {
        "Authorization": f"Bearer {GATEWAY_KEY}",
        "Content-Type": "application/json"
    }

    # 3. Выполняем запрос
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{GATEWAY_URL}/chat/completions", 
                json=payload, 
                headers=headers
            )
            
            # Обработка HTTP ошибок
            if resp.status_code != 200:
                logging.error(f"Gateway Error {resp.status_code}: {resp.text}")
                return f"⚠️ Агент {role} недоступен (Gateway Error {resp.status_code})."
            
            data = resp.json()
            return data['choices'][0]['message']['content']

    except httpx.RequestError as e:
        logging.error(f"Network Error calling {role}: {e}")
        return f"⚠️ Шлюз в Далласе не отвечает: {str(e)}"
    except Exception as e:
        logging.error(f"Unknown Error calling {role}: {e}")
        return f"⚠️ Внутренняя ошибка агента: {str(e)}"
