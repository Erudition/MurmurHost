FROM mumblevoip/mumble-server:alpine

COPY murmur.ini /etc/murmur.ini

EXPOSE 64738
