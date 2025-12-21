import os
import httpx
import logging

# Читаем конфиги из переменных окружения
GATEWAY_URL = os.getenv("GATEWAY_BASE_URL", "http://172.86.90.213:3000/v1")
GATEWAY_KEY = os.getenv("GATEWAY_API_KEY", "sk-gateway-alex-2025")

async def call_agent(role, prompt):
    """
    Отправляет запрос агенту через API Gateway в Далласе.
    """
    try:
        # 1. Загружаем системный промпт из файла
        # (Путь может отличаться на Render, используем относительный)
        profile_path = os.path.join(os.getcwd(), "bots", "ai_team", "profiles", f"{role}.txt")
        
        with open(profile_path, "r", encoding="utf-8") as f:
            system_instruction = f.read()

        # 2. Формируем запрос
        payload = {
            "model": "auto", # Шлюз сам выберет лучшую модель
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ]
        }
        
        headers = {
            "Authorization": f"Bearer {GATEWAY_KEY}",
            "Content-Type": "application/json"
        }

        # 3. Стучимся в Даллас
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{GATEWAY_URL}/chat/completions", 
                json=payload, 
                headers=headers
            )
            
            if resp.status_code != 200:
                logging.error(f"Gateway Error {resp.status_code}: {resp.text}")
                return f"⚠️ Агент {role} недоступен (Gateway Error)."
                
            data = resp.json()
            # Можно логировать, какая модель ответила: data['_gateway_info']['model_used']
            return data['choices'][0]['message']['content']

    except Exception as e:
        logging.error(f"Agent call failed: {e}")
        return f"⚠️ Ошибка вызова агента {role}: {str(e)}"
