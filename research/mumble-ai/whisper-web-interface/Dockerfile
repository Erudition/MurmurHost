# Stage 1: Build React frontend
FROM node:18-alpine AS frontend-builder

WORKDIR /app/client

# Copy package files
COPY client/package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY client/ ./

# Build the application
RUN npm run build

# Stage 2: Python backend with frontend
FROM python:3.11-slim

# Install system dependencies including ffmpeg and build tools
RUN apt-get update && \
    apt-get install -y ffmpeg gcc g++ make && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python application
COPY app.py .

# Copy built frontend from previous stage
COPY --from=frontend-builder /app/client/dist ./static

# Create temp directory for file uploads
RUN mkdir -p /tmp/whisper-uploads

# Expose port
EXPOSE 5008

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5008/health || exit 1

# Run the application
CMD ["python", "app.py"]
