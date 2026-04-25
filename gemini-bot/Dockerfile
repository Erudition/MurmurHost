FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libopus-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /bots

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
# Set PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python to avoid conflicts between Pipecat and pymumble
ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
RUN pip install --no-cache-dir -r requirements.txt
# MANDATORY SPEC: Install pymumble from git without deps
RUN pip install --no-cache-dir git+https://github.com/azlux/pymumble.git --no-deps

# Copy bot code
COPY . .

CMD ["python", "bot.py"]
