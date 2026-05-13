FROM python:3.11-slim

# Установка часового пояса и системных обновлений
ENV TZ=Europe/London
RUN apt-get update && apt-get install -y tzdata && \
    rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /root/ultra-trinity

# Копирование файла зависимостей
COPY requirements.txt .

# Установка библиотек без кэширования
RUN pip install --no-cache-dir -r requirements.txt

# Копирование монолита и базы данных
COPY . .

# Выдача прав на исполнение
RUN chmod +x radar_nexus.py

# Базовая команда
CMD ["python3", "radar_nexus.py"]
