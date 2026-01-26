FROM mumblevoip/mumble-server:latest

COPY murmur.ini /etc/murmur.ini
ENV MUMBLE_CUSTOM_CONFIG_FILE=/etc/murmur.ini

EXPOSE 64738
