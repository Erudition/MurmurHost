FROM python:3.10-slim

WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libopus0 \
    libopus-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy application files first
COPY bridge.py .
COPY config.py .
COPY memory_manager.py .
COPY requirements.txt .

# Install pymumble first (has dependency issues)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir pymumble==1.6.1

# Install other dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose SIP port
EXPOSE 5060/udp
EXPOSE 5060/tcp

CMD ["python", "bridge.py"]
