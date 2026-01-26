FROM ubuntu:24.04

RUN apt-get update && apt-get install -y mumble-server && \
    mkdir -p /data && \
    rm -rf /var/lib/apt/lists/*

COPY murmur.sqlite /data/mumble-server.sqlite
COPY murmur.ini /etc/murmur.ini
RUN chown -R mumble-server:mumble-server /data
ENV MUMBLE_CUSTOM_CONFIG_FILE=/etc/murmur.ini

EXPOSE 64738 64738/udp

CMD ["/usr/bin/mumble-server", "-fg", "-ini", "/etc/murmur.ini"]
