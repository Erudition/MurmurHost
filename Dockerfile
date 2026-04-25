FROM alpine:latest

# Install Murmur (Mumble Server) and Bash for healthchecks
RUN apk add --no-cache murmur bash && \
    mkdir -p /var/lib/murmur && \
    chown -R murmur:murmur /var/lib/murmur

# Copy configuration (Baked for production authority)
COPY murmur.ini /etc/murmur.ini

# Metadata
EXPOSE 64738 64738/udp

# Use the non-root 'murmur' user provided by the package
USER murmur

# Start Murmur in foreground mode
CMD ["mumble-server", "-fg", "-ini", "/etc/murmur.ini"]
