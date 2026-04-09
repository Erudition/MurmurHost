FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-zeroc-ice \
    zeroc-ice-slice \
    libvorbis-dev \
    libopus-dev \
    opus-tools \
    libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /bots

RUN pip3 install --no-cache-dir \
    "python-dotenv" \
    docker

RUN pip3 install --no-cache-dir git+https://github.com/azlux/pymumble.git

COPY supervisor_bot.py .
COPY Murmur.ice .
COPY mumo ./mumo

CMD ["python3", "-u", "supervisor_bot.py"]
