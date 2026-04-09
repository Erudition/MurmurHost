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
    && rm -rf /var/lib/apt/lists/*

WORKDIR /bots

RUN pip3 install --no-cache-dir \
    opuslib

RUN pip3 install --no-cache-dir git+https://github.com/azlux/pymumble.git

COPY opus_recorder.py .
COPY mumblerecbot ./mumblerecbot

CMD ["python3", "-u", "opus_recorder.py", "--name", "Recording"]
