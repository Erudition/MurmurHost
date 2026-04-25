FROM alpine:latest

# Install Murmur (Mumble Server), Bash, and Python3 for reliable healthchecks
RUN apk add --no-cache murmur bash python3 && \
    mkdir -p /var/lib/murmur && \
    chown -R murmur:murmur /var/lib/murmur

# Copy configuration and healthcheck script
COPY murmur.ini /etc/murmur.ini
COPY healthcheck.py /usr/local/bin/healthcheck.py
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

# BAKE the database as a seed (to escape bind-mount hell)
COPY db/murmur.sqlite /etc/murmur/murmur.sqlite.seed

# Ensure scripts are executable
RUN chmod +x /usr/local/bin/healthcheck.py /usr/local/bin/entrypoint.sh

# Metadata
EXPOSE 64738 64738/udp

# Use the entrypoint to handle permission and SEEDING
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
