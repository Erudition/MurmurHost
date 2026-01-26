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

# Install pymumble and zeroc-ice
RUN pip3 install pymumble zeroc-ice

WORKDIR /bots

# Copy scripts and directories
COPY echobot.py .
COPY opus_recorder.py .
COPY Murmur.ice .
COPY startup.sh .
COPY mumo ./mumo
COPY mumblerecbot ./mumblerecbot

# Make startup script executable
RUN chmod +x startup.sh

# Run the startup script
CMD ["/bots/startup.sh"]
