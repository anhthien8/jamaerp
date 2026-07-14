FROM python:3.12-slim

WORKDIR /app

# Support both root-level and backend-level build contexts
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Non-root user
RUN groupadd -r app && useradd -r -g app app
USER app

# Health server starts immediately — Railway healthcheck hits this
ENTRYPOINT ["python", "-c", "from http.server import HTTPServer, BaseHTTPRequestHandler; import threading,os;class H(BaseHTTPRequestHandler):\\n  def do_GET(self):\\n    self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{\"status\":\"ok\"}')\\n  def log_message(self,*a):pass\\nHTTPServer(('0.0.0.0',8080),H).serve_forever()"]

# App starts after health server is up
CMD ["sh", "-c", "sleep 2 && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
