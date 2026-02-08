FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ECS-friendly: bind on 0.0.0.0 and use env PORT
CMD ["sh", "-c", "gunicorn -w 2 -b 0.0.0.0:${PORT:-8000} app:app"]
