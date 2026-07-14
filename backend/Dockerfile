FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN groupadd -r app && useradd -r -g app app
RUN chmod +x start.sh
USER app

# Health server on 8080 + app on $PORT (8000 default)
CMD ["./start.sh"]
