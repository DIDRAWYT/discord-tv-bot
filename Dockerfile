FROM python:3.11-slim

WORKDIR /app

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта
COPY . .

# Создаем папку для ключей и копируем туда JSON
RUN mkdir -p /app/keys
COPY google-key.json /app/keys/google-key.json

# Запускаем бота
CMD ["python", "bot.py"]
