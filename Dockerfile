FROM python:3.10-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    httpx \
    beautifulsoup4 \
    "python-telegram-bot[job-queue]" \
    python-dotenv

COPY . .

CMD ["python", "main.py"]
