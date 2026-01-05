# Используем легкий Linux (Debian-based) с Python 3.10
FROM python:3.10-slim

# Устанавливаем рабочую папку
WORKDIR /app

# 1. ГЛАВНОЕ: Установка системных библиотек (ffmpeg)
# Без этого блока голосовые не заработают
RUN apt-get update && \
    apt-get install -y ffmpeg flac && \
    rm -rf /var/lib/apt/lists/*

# 2. Копируем файл зависимостей
COPY requirements.txt .

# 3. Устанавливаем Python-библиотеки
RUN pip install --no-cache-dir -r requirements.txt

# 4. Копируем весь код проекта в контейнер
COPY . .

# 5. Команда запуска твоего мультибота
CMD ["python", "main.py"]
