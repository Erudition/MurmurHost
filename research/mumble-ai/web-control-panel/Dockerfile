FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY templates templates/
COPY download_voices.py .

# Create piper voices directory
RUN mkdir -p /app/piper_voices

# Note: Voices will be downloaded at runtime to the mounted volume

EXPOSE 5002

CMD ["python", "app.py"]
