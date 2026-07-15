FROM python:3.12-slim

WORKDIR /app

COPY telegram-bot/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY telegram-bot/ .

CMD ["python", "-m", "bot.main"]
