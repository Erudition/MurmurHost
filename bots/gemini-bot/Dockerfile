FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libopus0 \
    libopus-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir "pipecat-ai[google]" "pipecat-ai[silero]"


COPY . .

CMD ["python", "bot.py"]
