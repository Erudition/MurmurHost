FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    libvorbis-dev \
    libopus-dev \
    opus-tools \
    libssl-dev \
    git \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /bots

RUN pip3 install --no-cache-dir \
    "pipecat-ai[google,silero]>=0.0.108" \
    "python-dotenv" \
    opuslib

RUN pip3 install --no-cache-dir --no-deps git+https://github.com/azlux/pymumble.git

ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

COPY . .

CMD ["python3", "-u", "pipecat_bot.py"]
