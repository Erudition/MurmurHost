FROM alpine:latest

# Install Murmur (Mumble Server), Bash, and Python3 for reliable healthchecks
RUN apk add --no-cache murmur bash python3 && \
    mkdir -p /var/lib/murmur && \
    chown -R murmur:murmur /var/lib/murmur

# Copy configuration and healthcheck script
COPY murmur.ini /etc/murmur.ini
COPY healthcheck.py /usr/local/bin/healthcheck.py

# Metadata
EXPOSE 64738 64738/udp

# Use the non-root 'murmur' user provided by the package
USER murmur

# Start Murmur in foreground mode
CMD ["mumble-server", "-fg", "-ini", "/etc/murmur.ini"]
