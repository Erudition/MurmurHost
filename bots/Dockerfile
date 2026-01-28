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
    opus-tools \
    libssl-dev \
    libbz2-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install pymumble, zeroc-ice, and google-genai
RUN pip3 install pymumble zeroc-ice google-genai

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

# Install ffmpeg for Testing Bot
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Make startup script executable
RUN chmod +x startup.sh

# Run the Supervisor Bot
CMD ["python3", "/bots/supervisor_bot.py"]
