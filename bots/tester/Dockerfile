FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libopus-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /bots

# Install Python dependencies
# Set PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python to avoid conflicts
ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
# MANDATORY SPEC: Install pymumble from git without deps
RUN pip install --no-cache-dir git+https://github.com/azlux/pymumble.git --no-deps

# Copy bot code
COPY certs ./certs
COPY clips ./clips
COPY main.py .

CMD ["python", "main.py"]
