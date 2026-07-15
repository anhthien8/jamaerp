FROM python:3.12-slim

ARG SERVICE=backend

WORKDIR /app

# Backend service
RUN if [ "$SERVICE" = "backend" ]; then \
      cp backend/requirements.txt ./requirements.txt && \
      pip install --no-cache-dir -r requirements.txt && \
      cp -r backend/. . ; \
    fi

# Telegram-bot service
RUN if [ "$SERVICE" = "telegram-bot" ]; then \
      cp telegram-bot/requirements.txt ./requirements.txt && \
      pip install --no-cache-dir -r requirements.txt && \
      cp -r telegram-bot/. . ; \
    fi

RUN groupadd -r app && useradd -r -g app app
RUN if [ "$SERVICE" = "backend" ]; then chmod +x start.sh; fi
USER app

# Start command varies by service
CMD if [ "$SERVICE" = "backend" ]; then \
      exec ./start.sh; \
    else \
      exec python -m bot.main; \
    fi
