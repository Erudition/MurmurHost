FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install piper-tts
RUN pip install --no-cache-dir \
    piper-tts \
    flask \
    psycopg2-binary

# Copy application files
COPY app.py .
COPY download_model.py .

# Create models directory
RUN mkdir -p /app/models

# Download a default voice model
RUN python download_model.py

EXPOSE 5001

CMD ["python", "app.py"]
