FROM ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-zeroc-ice \
    zeroc-ice-slice \
    libvorbis-dev \
    libopus-dev \
    opus-tools \
    libssl-dev \
    libbz2-dev \
    git \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /bots

# Copy scripts and directories
COPY echobot.py .
COPY opus_recorder.py .
COPY supervisor_bot.py .
COPY test_bot.py .
COPY Murmur.ice .
COPY startup.sh .
COPY mumo ./mumo
COPY mumblerecbot ./mumblerecbot
COPY gemini-bot ./gemini-bot

# Make startup script executable
RUN chmod +x startup.sh

# Install Python dependencies
# We install pipecat-ai first (which pull in newer protobuf)
RUN pip3 install --no-cache-dir \
    "pipecat-ai[google,silero]>=0.0.45" \
    "python-dotenv" \
    opuslib

# We install pymumble from git with --no-deps to skip the strict protobuf==3.20.3 requirement.
# ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python (set below) will allow it to run.
RUN pip3 install --no-cache-dir --no-deps git+https://github.com/azlux/pymumble.git

# Install remaining requirements
RUN pip3 install --no-cache-dir -r gemini-bot/requirements.txt

# Fix Protobuf conflict
ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

# Run the Supervisor Bot
CMD ["python3", "-u", "/bots/supervisor_bot.py"]
